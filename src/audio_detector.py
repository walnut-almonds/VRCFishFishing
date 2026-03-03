# audio_detector.py - 咬勾音效偵測
#
# 主要方案：正規化波形互相關（需提供 assets/bite_sound.wav）
# 備援方案：Bandpass RMS 閾值（無錄音檔時自動切換）
#
# 使用 sounddevice 的 loopback 模式監聽系統音訊輸出，
# 不需要任何麥克風，直接捕捉遊戲播放的音效。

import importlib
import os
import queue
import threading
import time
from typing import Any, cast

import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal
import sounddevice as sd

# 可選：WASAPI loopback 備援
try:
    sc = importlib.import_module("soundcard")
except Exception:
    sc = None

try:
    pythoncom = importlib.import_module("pythoncom")
except Exception:
    pythoncom = None
from src.config import (
    AUDIO_CHANNELS,
    AUDIO_CHUNK_SIZE,
    AUDIO_COOLDOWN,
    AUDIO_DEBUG_CORR,
    AUDIO_DEBUG_RMS,
    AUDIO_DEBUG_RMS_INTERVAL,
    AUDIO_SAMPLE_RATE,
    BITE_CORR_HIT_STREAK,
    BITE_CORR_MARGIN,
    BITE_CORR_THRESHOLD,
    BITE_RMS_BANDPASS,
    BITE_RMS_MULTIPLIER,
    BITE_SOUND_PATH,
)
from src.utils import log

# 相容性修正：soundcard 目前仍可能呼叫 np.fromstring(binary)
# 但 NumPy 2.x 已移除 binary mode，需轉用 np.frombuffer。
_np_fromstring_original = np.fromstring


def _np_fromstring_compat(string, dtype=float, count=-1, sep=""):
    # NumPy 2.x 移除 binary mode fromstring；
    # soundcard 會傳入 cffi buffer（非 bytes），因此不能只判斷 isinstance。
    if sep == "":
        try:
            return np.frombuffer(string, dtype=dtype, count=count)
        except Exception:
            pass
    return _np_fromstring_original(string, dtype=dtype, count=count, sep=sep)


cast(Any, np).fromstring = _np_fromstring_compat

# soundcard.mediafoundation 內部使用自身的 numpy 參照，顯式覆蓋其 fromstring
if sc is not None:
    try:
        _sc_mf = importlib.import_module("soundcard.mediafoundation")
        cast(Any, _sc_mf.numpy).fromstring = _np_fromstring_compat
    except Exception:
        pass


class AudioDetector:
    """
    在背景執行緒持續監聽系統音訊，偵測到咬勾音效時設定 triggered 旗標。
    """

    def __init__(self):
        self.triggered = threading.Event()
        self._active = False
        self._thread: threading.Thread | None = None
        self._cooldown_until = 0.0

        # 嘗試載入參考音效
        self._ref_wave: np.ndarray | None = None
        self._use_corr = False
        self._load_reference()

        # RMS 備援用的靜默基準（動態校準）
        self._rms_baseline = 0.01
        self._last_rms = 0.0
        self._corr_hit_streak = 0

    # ── 初始化 ────────────────────────────────────────────────────────────────

    def _load_reference(self):
        if not os.path.exists(BITE_SOUND_PATH):
            log(f"[Audio] 找不到 {BITE_SOUND_PATH}，改用 RMS 備援方案")
            return

        try:
            rate, data = wavfile.read(BITE_SOUND_PATH)
            # 轉換為單聲道 float32
            if data.ndim > 1:
                data = data.mean(axis=1)
            data = data.astype(np.float32)
            # 重採樣至目標取樣率
            if rate != AUDIO_SAMPLE_RATE:
                num = int(len(data) * AUDIO_SAMPLE_RATE / rate)
                data = signal.resample(data, num)
            # 正規化
            mx = np.max(np.abs(data))
            if mx > 0:
                data /= mx
            self._ref_wave = data
            self._use_corr = True
            log(
                f"[Audio] 載入參考音效 ({len(data)} samples @ {AUDIO_SAMPLE_RATE}Hz)，使用互相關方案"
            )
        except Exception as e:
            log(f"[Audio] 載入參考音效失敗：{e}，改用 RMS 備援方案")

    # ── 公開介面 ──────────────────────────────────────────────────────────────

    def start(self):
        """啟動背景監聽執行緒。"""
        if self._active:
            return
        self._active = True
        self.triggered.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log("[Audio] 監聽執行緒已啟動")

    def stop(self):
        """停止背景監聽執行緒。"""
        self._active = False
        if self._thread:
            self._thread.join(timeout=2.0)
        log("[Audio] 監聽執行緒已停止")

    def clear(self):
        """清除觸發旗標（在進入 TENSION 後呼叫）。"""
        self.triggered.clear()

    def wait_for_bite(self, timeout: float) -> bool:
        """
        阻塞等待咬勾訊號，最多等待 timeout 秒。
        回傳 True 表示偵測到咬勾，False 表示超時。
        """
        return self.triggered.wait(timeout=timeout)

    # ── 背景監聽 ──────────────────────────────────────────────────────────────

    def _listen_loop(self):
        """背景執行緒：持續讀取系統音訊並判斷是否咬勾。"""
        # 滾動緩衝區，長度為參考波形的 2 倍（確保能找到完整匹配）
        buf_size = (
            len(self._ref_wave) * 2
            if self._ref_wave is not None
            else AUDIO_CHUNK_SIZE * 4
        )
        buffer = np.zeros(buf_size, dtype=np.float32)

        # 嘗試取得 loopback 裝置（WASAPI loopback）
        device_idx = self._find_loopback_device()

        # 設定 WASAPI loopback 模式（Windows 專用），不設定此項則抓到的是麥克風而非遊戲音效
        wasapi_settings: Any = None
        wasapi_loopback_supported = False
        try:
            wasapi_settings = cast(Any, sd.WasapiSettings)(loopback=True)
            wasapi_loopback_supported = True
        except TypeError as e:
            # 某些 sounddevice/PortAudio 組合沒有 loopback 參數
            # （此時即使有 WASAPI 也無法透過 sounddevice 直接啟用 loopback）
            log(f"[Audio] 目前 sounddevice 不支援 loopback 參數：{e}")
            try:
                wasapi_settings = cast(Any, sd.WasapiSettings)()
            except Exception:
                wasapi_settings = None
        except Exception as e:
            log(f"[Audio] WasapiSettings 初始化失敗：{e}")

        # 只有「輸出裝置」才能使用 WASAPI loopback
        use_loopback = False
        if (
            wasapi_loopback_supported
            and wasapi_settings is not None
            and device_idx is not None
        ):
            try:
                dev = sd.query_devices(device_idx)
                use_loopback = int(dev.get("max_output_channels", 0)) > 0
                if not use_loopback:
                    log(
                        "[Audio] 目前裝置非輸出端，無法啟用 WASAPI loopback，改用一般輸入模式"
                    )
            except Exception:
                use_loopback = False
        elif not wasapi_loopback_supported:
            log(
                "[Audio] 此環境的 sounddevice 無法啟用 WASAPI loopback，將退回一般輸入模式"
            )
            # 優先改走 soundcard 的喇叭 loopback，避免誤用無訊號的 Stereo Mix
            if self._try_soundcard_loopback(device_idx):
                return
            log(
                "[Audio] soundcard loopback 不可用，才改用一般輸入裝置（可能是麥克風/Stereo Mix）"
            )

        # 非 loopback 模式下，不能使用「純輸出」裝置當 InputStream
        # （其 max_input_channels 常為 0，會觸發 Invalid number of channels）
        if not use_loopback and device_idx is not None:
            try:
                dev = sd.query_devices(device_idx)
                if int(dev.get("max_input_channels", 0)) <= 0:
                    log(
                        "[Audio] 目前裝置是輸出端且無輸入聲道，改用可錄音裝置（Stereo Mix/預設輸入）"
                    )
                    device_idx = self._find_recording_input_device()
            except Exception:
                device_idx = self._find_recording_input_device()

        try:
            # 盡量使用裝置預設取樣率避免 Invalid sample rate，
            # 再於後續將 chunk 重採樣回 AUDIO_SAMPLE_RATE 做偵測。
            stream_rate = AUDIO_SAMPLE_RATE
            if device_idx is not None:
                try:
                    stream_rate = int(
                        sd.query_devices(device_idx).get(
                            "default_samplerate", AUDIO_SAMPLE_RATE
                        )
                    )
                except Exception:
                    stream_rate = AUDIO_SAMPLE_RATE
            stream_rate = max(8000, stream_rate)
            stream_blocksize = max(
                256, int(AUDIO_CHUNK_SIZE * stream_rate / AUDIO_SAMPLE_RATE)
            )

            stream_kwargs: dict[str, Any] = dict(
                samplerate=stream_rate,
                dtype="float32",
                blocksize=stream_blocksize,
                device=device_idx,
            )
            if use_loopback:
                stream_kwargs["extra_settings"] = wasapi_settings
                # loopback 模式下以輸出聲道數為準（通常是 2）
                if device_idx is not None:
                    out_ch = sd.query_devices(device_idx).get("max_output_channels", 0)
                    stream_kwargs["channels"] = (
                        min(2, int(out_ch)) if int(out_ch) > 0 else 2
                    )
                else:
                    stream_kwargs["channels"] = 2
            else:
                # 一般輸入模式下，聲道數不能超過 max_input_channels
                if device_idx is not None:
                    max_in = int(
                        sd.query_devices(device_idx).get("max_input_channels", 0)
                    )
                    stream_kwargs["channels"] = min(
                        max(1, AUDIO_CHANNELS), max(1, max_in)
                    )
                else:
                    stream_kwargs["channels"] = AUDIO_CHANNELS

            # 使用 callback 模式避免 WDM-KS 下 Blocking API not supported 錯誤
            audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=32)

            def _audio_callback(
                indata: np.ndarray,
                frames: int,
                tinfo: Any,
                status: Any,
            ) -> None:
                if status:
                    log(f"[Audio] callback 狀態：{status}")
                chunk = indata[:, 0] if indata.ndim > 1 else indata.flatten()
                if stream_rate != AUDIO_SAMPLE_RATE and len(chunk) > 8:
                    target_len = max(
                        1, int(len(chunk) * AUDIO_SAMPLE_RATE / stream_rate)
                    )
                    chunk = signal.resample(chunk, target_len).astype(np.float32)
                try:
                    audio_q.put_nowait(chunk.copy())
                except queue.Full:
                    # 滿了就丟掉最舊一筆，避免 callback 被阻塞
                    try:
                        _ = audio_q.get_nowait()
                        audio_q.put_nowait(chunk.copy())
                    except Exception:
                        pass

            stream_kwargs["callback"] = _audio_callback

            with sd.InputStream(**stream_kwargs):
                dev_name = (
                    sd.query_devices(device_idx)["name"]
                    if device_idx is not None
                    else "預設"
                )
                log(
                    f"[Audio] 使用裝置：{dev_name}（loopback={'是' if use_loopback else '否'}，sr={stream_rate}）"
                )
                last_rms_log_t = 0.0
                while self._active:
                    try:
                        chunk = audio_q.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    # 即時 RMS（裝置有無聲音的快速診斷）
                    self._last_rms = float(np.sqrt(np.mean(chunk**2)))
                    if AUDIO_DEBUG_RMS:
                        now = time.time()
                        if now - last_rms_log_t >= AUDIO_DEBUG_RMS_INTERVAL:
                            log(
                                f"[Audio][RMS] device={dev_name}, rms={self._last_rms:.6f}"
                            )
                            last_rms_log_t = now

                    # 更新滾動緩衝區
                    buffer = np.roll(buffer, -len(chunk))
                    buffer[-len(chunk) :] = chunk

                    if time.time() < self._cooldown_until:
                        continue

                    if self._use_corr:
                        self._check_correlation(buffer)
                    else:
                        self._check_rms(chunk)

        except Exception as e:
            log(f"[Audio] 串流錯誤：{e}")

            # 若 PortAudio 路徑失敗，嘗試用 soundcard 做系統輸出 loopback 備援
            if self._try_soundcard_loopback(device_idx):
                return

    def _find_loopback_device(self) -> int | None:
        """
        在 Windows 上搜尋可用於 loopback 的裝置。
        WASAPI loopback 是把「輸出裝置」當輸入來抓，因此目標裝置
        max_input_channels 為 0 是正常的，不應以此排除。
        """
        devices = sd.query_devices()

        # 主要路徑：WASAPI loopback 直接使用「輸出裝置」
        try:
            hostapis = sd.query_hostapis()
            wasapi_api_indices = {
                i
                for i, api in enumerate(hostapis)
                if "wasapi" in str(api.get("name", "")).lower()
            }

            # 優先使用 WASAPI 的預設輸出裝置
            for api in hostapis:
                if "wasapi" in api["name"].lower():
                    default_out = api.get("default_output_device", -1)
                    if default_out >= 0:
                        dev = sd.query_devices(default_out)
                        if int(dev.get("max_output_channels", 0)) > 0:
                            log(
                                f"[Audio] 使用 WASAPI 預設輸出裝置作為 loopback: {dev['name']} "
                                f"(out_ch={dev['max_output_channels']})"
                            )
                            return default_out

            # 次選：任一 WASAPI 輸出裝置
            for i, dev in enumerate(devices):
                if (
                    int(dev.get("hostapi", -1)) in wasapi_api_indices
                    and int(dev.get("max_output_channels", 0)) > 0
                ):
                    log(
                        f"[Audio] 使用 WASAPI 輸出裝置作為 loopback: {dev['name']} "
                        f"(out_ch={dev['max_output_channels']})"
                    )
                    return i
        except Exception:
            pass

        # 次選：Stereo Mix / 立體聲混音（需在 Windows 音效設定中手動啟用）
        # 優先避開 WDM-KS，因其 blocking API 可能不支援
        stereo_candidates = []
        for i, dev in enumerate(devices):
            name_lower = dev["name"].lower()
            if (
                any(
                    k in name_lower
                    for k in ("stereo mix", "立體聲混音", "what u hear", "混音")
                )
                and dev["max_input_channels"] > 0
            ):
                api_idx = int(dev.get("hostapi", -1))
                api_name = ""
                try:
                    api_name = (
                        sd.query_hostapis(api_idx)["name"].lower()
                        if api_idx >= 0
                        else ""
                    )
                except Exception:
                    api_name = ""

                # 分數越小越優先：WASAPI/MME/DS 優先，WDM-KS 最後
                if "wasapi" in api_name:
                    score = 0
                elif "mme" in api_name or "directsound" in api_name:
                    score = 1
                elif "wdm-ks" in api_name:
                    score = 3
                else:
                    score = 2
                stereo_candidates.append((score, i, dev["name"], api_name))

        if stereo_candidates:
            stereo_candidates.sort(key=lambda x: x[0])
            _, idx, name, api = stereo_candidates[0]
            log(f"[Audio] 找到 Stereo Mix 裝置: {name} (api={api})")
            return idx

        log("[Audio] 找不到 loopback 裝置，使用預設輸入裝置（可能為麥克風）")
        return None

    def _find_recording_input_device(self) -> int | None:
        """找可用的錄音輸入裝置（優先 Stereo Mix，否則預設輸入）。"""
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                name_lower = str(dev.get("name", "")).lower()
                if int(dev.get("max_input_channels", 0)) > 0 and any(
                    k in name_lower
                    for k in ("stereo mix", "立體聲混音", "what u hear", "混音")
                ):
                    log(f"[Audio] 改用 Stereo Mix 輸入: {dev['name']}")
                    return i

            default_in = (
                sd.default.device[0]
                if isinstance(sd.default.device, (list, tuple))
                else None
            )
            if default_in is not None and int(default_in) >= 0:
                dev = sd.query_devices(int(default_in))
                if int(dev.get("max_input_channels", 0)) > 0:
                    log(f"[Audio] 改用預設輸入裝置: {dev['name']}")
                    return int(default_in)
        except Exception:
            pass

        log("[Audio] 找不到可用錄音輸入裝置，將交由 sounddevice 自行選擇預設")
        return None

    def _try_soundcard_loopback(self, device_idx: int | None) -> bool:
        """嘗試用 soundcard 套件抓系統輸出 loopback（PortAudio 失敗時備援）。"""
        if sc is None:
            log("[Audio] soundcard 備援不可用（未安裝 soundcard）")
            return False

        # soundcard/WASAPI 依賴 COM；背景執行緒需先 CoInitialize
        com_inited = False
        if pythoncom is not None:
            try:
                co_initialize = getattr(pythoncom, "CoInitialize", None)
                if callable(co_initialize):
                    co_initialize()
                    com_inited = True
            except Exception as e:
                log(f"[Audio] COM 初始化失敗：{e}")

        target_name = None
        if device_idx is not None:
            try:
                dev = sd.query_devices(device_idx)
                if int(dev.get("max_output_channels", 0)) > 0:
                    target_name = str(dev.get("name", ""))
            except Exception:
                target_name = None

        try:
            loopback_mic = None
            mics = sc.all_microphones(include_loopback=True)

            # 先選「Loopback 麥克風」中與目標輸出裝置同名者
            # （soundcard 會把喇叭 loopback 暴露成 Microphone 介面）
            if target_name:
                target_key = target_name.strip().lower()
                for mic in mics:
                    rep = str(mic).lower()
                    if "loopback" in rep and mic.name.lower() == target_key:
                        loopback_mic = mic
                        break

                if loopback_mic is None:
                    # 次選：名稱部分匹配
                    short_key = target_name.split("(")[0].strip().lower()
                    for mic in mics:
                        rep = str(mic).lower()
                        if (
                            "loopback" in rep
                            and short_key
                            and short_key in mic.name.lower()
                        ):
                            loopback_mic = mic
                            break

            # 若無指定目標，取第一個 loopback 麥克風
            if loopback_mic is None:
                for mic in mics:
                    if "loopback" in str(mic).lower():
                        loopback_mic = mic
                        break

            if loopback_mic is None:
                log("[Audio] soundcard 找不到可用的 loopback 麥克風")
                return False

            log(f"[Audio] 啟用 soundcard loopback 備援：{loopback_mic}")
            buf_size = (
                len(self._ref_wave) * 2
                if self._ref_wave is not None
                else AUDIO_CHUNK_SIZE * 4
            )
            buffer = np.zeros(buf_size, dtype=np.float32)
            last_rms_log_t = 0.0

            with loopback_mic.recorder(
                samplerate=AUDIO_SAMPLE_RATE, channels=1, blocksize=AUDIO_CHUNK_SIZE
            ) as rec:
                while self._active:
                    data = rec.record(numframes=AUDIO_CHUNK_SIZE)
                    chunk = data[:, 0] if data.ndim > 1 else data.flatten()

                    self._last_rms = float(np.sqrt(np.mean(chunk**2)))
                    if AUDIO_DEBUG_RMS:
                        now = time.time()
                        if now - last_rms_log_t >= AUDIO_DEBUG_RMS_INTERVAL:
                            log(
                                f"[Audio][RMS] device={loopback_mic.name}, rms={self._last_rms:.6f}"
                            )
                            last_rms_log_t = now

                    buffer = np.roll(buffer, -len(chunk))
                    buffer[-len(chunk) :] = chunk

                    if time.time() < self._cooldown_until:
                        continue

                    if self._use_corr:
                        self._check_correlation(buffer)
                    else:
                        self._check_rms(chunk)

            return True
        except Exception as e:
            log(f"[Audio] soundcard loopback 備援失敗：{e}")
            return False
        finally:
            if com_inited and pythoncom is not None:
                try:
                    co_uninitialize = getattr(pythoncom, "CoUninitialize", None)
                    if callable(co_uninitialize):
                        co_uninitialize()
                except Exception:
                    pass

    # ── 互相關方案 ────────────────────────────────────────────────────────────

    def _check_correlation(self, buffer: np.ndarray):
        ref = self._ref_wave
        if ref is None:
            self._corr_hit_streak = 0
            return

        ref_arr = np.asarray(ref, dtype=np.float32)
        buf_arr = np.asarray(buffer, dtype=np.float32)

        # 幾乎無聲，略過
        mx = np.max(np.abs(buf_arr))
        if mx < 1e-4:
            self._corr_hit_streak = 0
            return

        # 真正的 NCC（normalized cross-correlation）
        # 可容忍整體音量差異，對實際遊戲環境更穩定。
        ref_z = ref_arr - float(np.mean(ref_arr, dtype=np.float64))
        buf_z = buf_arr - float(np.mean(buf_arr, dtype=np.float64))

        # 避免近靜音片段造成 NCC 數值不穩定
        buf_power = float(np.mean(buf_z**2))
        if buf_power < 1e-8:
            self._corr_hit_streak = 0
            return

        ref_norm = float(np.linalg.norm(ref_z)) + 1e-10
        corr = signal.correlate(buf_z, ref_z, mode="valid", method="fft")

        # 每個對齊位置對應的 buffer 區段能量
        win = np.ones(len(ref_z), dtype=np.float32)
        energy = signal.convolve(buf_z**2, win, mode="valid")
        buf_energy = np.sqrt(np.clip(energy, 0.0, None)) + 1e-10

        corr_norm = corr / (ref_norm * buf_energy)
        corr_norm = np.nan_to_num(corr_norm, nan=-1.0, posinf=1.0, neginf=-1.0)

        peak_idx = int(np.argmax(corr_norm))
        peak = float(corr_norm[peak_idx])

        # 與次峰比較：短音效更容易出現偶發高峰，要求峰值要「明顯突出」
        exclusion = max(1, int(0.02 * AUDIO_SAMPLE_RATE))  # ±20ms
        lo = max(0, peak_idx - exclusion)
        hi = min(len(corr_norm), peak_idx + exclusion + 1)
        second_candidates = np.concatenate((corr_norm[:lo], corr_norm[hi:]))
        second_peak = (
            float(np.max(second_candidates)) if second_candidates.size > 0 else -1.0
        )
        peak_margin = peak - second_peak

        is_hit = (peak >= BITE_CORR_THRESHOLD) and (peak_margin >= BITE_CORR_MARGIN)
        if is_hit:
            self._corr_hit_streak += 1
        else:
            self._corr_hit_streak = 0

        if AUDIO_DEBUG_CORR:
            log(
                f"[Audio] 互相關峰值：peak={peak:.3f}, second={second_peak:.3f}, "
                f"margin={peak_margin:.3f}, streak={self._corr_hit_streak}"
            )
        if self._corr_hit_streak >= max(1, int(BITE_CORR_HIT_STREAK)):
            log(f"[Audio] 互相關觸發！peak={peak:.3f}, margin={peak_margin:.3f}")
            self._corr_hit_streak = 0
            self._trigger()

    # ── RMS 備援方案 ──────────────────────────────────────────────────────────

    def _check_rms(self, chunk: np.ndarray):
        rms = float(np.sqrt(np.mean(chunk**2)))

        # 動態更新靜默基準（低通平均）
        self._rms_baseline = self._rms_baseline * 0.98 + rms * 0.02

        if rms > self._rms_baseline * BITE_RMS_MULTIPLIER:
            # 額外做 bandpass 確認
            if self._bandpass_energy(chunk):
                log(
                    f"[Audio] RMS 觸發！rms={rms:.4f}, baseline={self._rms_baseline:.4f}"
                )
                self._trigger()

    def _bandpass_energy(self, chunk: np.ndarray) -> bool:
        """檢查 chunk 在目標頻段的能量是否佔主導。"""
        lo, hi = BITE_RMS_BANDPASS
        nyq = AUDIO_SAMPLE_RATE / 2
        b, a = signal.butter(4, [lo / nyq, hi / nyq], btype="band")
        filtered = signal.lfilter(b, a, chunk)
        orig_energy = float(np.mean(chunk**2)) + 1e-10
        filt_energy = float(np.mean(filtered**2))
        return (filt_energy / orig_energy) > 0.3

    # ── 觸發 ──────────────────────────────────────────────────────────────────

    def _trigger(self):
        self.triggered.set()
        self._cooldown_until = time.time() + AUDIO_COOLDOWN
