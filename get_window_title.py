"""
視窗標題獲取工具
此腳本列出系統中所有打開的視窗與標題
"""

import pygetwindow as gw


def list_all_windows():
    """列出所有視窗"""
    print("=" * 60)
    print("當前所有打開的視窗:")
    print("=" * 60)

    windows = gw.getAllWindows()

    # 過濾掉空標題的視窗
    valid_windows = [w for w in windows if w.title.strip()]

    if not valid_windows:
        print("未找到任何視窗")
        return

    for i, window in enumerate(valid_windows, 1):
        print(f"\n{i}. 視窗標題: {window.title}")
        print(f"   位置: ({window.left}, {window.top})")
        print(f"   大小: {window.width}x{window.height}")
        print(
            f"   狀態: {'最小化' if window.isMinimized else '正常' if window.isActive else '後台'}"
        )

    print("\n" + "=" * 60)
    print(f"共找到 {len(valid_windows)} 個視窗")
    print("=" * 60)
    print("\n提示: 複製你的遊戲視窗標題到 config.yaml 檔案中")


def search_window(keyword: str):
    """根據關鍵詞搜索視窗"""
    print(f"\n搜索包含 '{keyword}' 的視窗:")
    print("-" * 60)

    windows = gw.getWindowsWithTitle(keyword)

    if not windows:
        print(f"未找到包含 '{keyword}' 的視窗")
        return

    for i, window in enumerate(windows, 1):
        print(f"{i}. {window.title}")

    print(f"\n找到 {len(windows)} 個匹配的視窗")


if __name__ == "__main__":
    print("\n===== 視窗標題獲取工具 =====\n")
    print("1. 顯示所有視窗")
    print("2. 搜索特定視窗")
    print("0. 退出")

    while True:
        choice = input("\n請選擇 (1/2/0): ").strip()

        if choice == "1":
            list_all_windows()
        elif choice == "2":
            keyword = input("請輸入搜索關鍵詞: ").strip()
            if keyword:
                search_window(keyword)
            else:
                print("關鍵詞不能為空")
        elif choice == "0":
            print("退出程式")
            break
        else:
            print("無效選擇，請重新輸入")
