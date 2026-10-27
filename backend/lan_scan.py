#!/usr/bin/env python3
import subprocess
import ipaddress
import threading
import time
import platform

# 限制同时 ping 的数量，防止把系统 ping 崩溃（50个并发足够快，且不伤路由器）
SEMAPHORE = threading.Semaphore(50)
LOCK = threading.Lock()

# 存放结果
active_ips = []
inactive_ips = []


def ping_ip(ip_str):
    """
    根据操作系统发送 ping 命令
    返回 True 表示 IP 在线（有人用），False 表示离线或超时
    """
    system = platform.system().lower()
    if system == 'windows':
        # Windows: -n 1 发1次, -w 1000 超时1秒
        cmd = ['ping', '-n', '1', '-w', '1000', ip_str]
    else:
        # Linux / Mac: -c 1 发1次, -W 1 超时1秒
        cmd = ['ping', '-c', '1', '-W', '1', ip_str]

    try:
        # 不显示任何输出，只看返回码
        ret = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ret.returncode == 0
    except Exception:
        return False


def scan_worker(ip):
    """线程工作函数"""
    with SEMAPHORE:  # 控制并发数
        ip_str = str(ip)
        is_active = ping_ip(ip_str)

        with LOCK:
            if is_active:
                active_ips.append(ip_str)
                # 只打印活跃的，减少刷屏
                print(f"✅ 占用: {ip_str}")
            else:
                inactive_ips.append(ip_str)


def main():
    # 设定要扫描的网段（根据你的教室网络）
    network = ipaddress.ip_network('192.168.14.0/24', strict=False)
    hosts = list(network.hosts())  # 排除 .0 和 .255

    print(f"🔍 开始扫描 {len(hosts)} 个 IP (192.168.14.1 - 192.168.14.254)")
    print("⏳ 预计耗时 5~10 秒，请稍候...\n")

    start_time = time.time()

    # 创建并启动线程
    threads = []
    for ip in hosts:
        t = threading.Thread(target=scan_worker, args=(ip,))
        t.start()
        threads.append(t)

    # 等待所有线程结束
    for t in threads:
        t.join()

    end_time = time.time()

    # 打印统计结果
    print("\n" + "=" * 50)
    print(f"✅ 扫描完成！总耗时: {end_time - start_time:.2f} 秒")
    print(f"📌 已占用 (活跃): {len(active_ips)} 个")
    print(f"🟢 可能空闲: {len(inactive_ips)} 个")

    # 推荐 IP：优先从 200-254 之间选空闲的（教室手动配通常用这段）
    recommend_ips = []
    for ip in inactive_ips:
        # 提取最后一段数字
        last_octet = int(ip.split('.')[-1])
        if 200 <= last_octet <= 254:
            recommend_ips.append(ip)

    # 如果 200-254 段全满，则随便推荐前 10 个空闲的
    if not recommend_ips:
        recommend_ips = inactive_ips[:10]

    print("\n🎯 推荐使用的空闲 IP (建议挑 210~250 之间的):")
    for i, ip in enumerate(recommend_ips[:15], 1):
        print(f"   {i}. {ip}")

    # 额外提醒
    print("\n💡 提示: 选好后在虚拟机执行以下命令临时生效:")
    print("   sudo ip addr add 你选的IP/24 dev ens33")
    print("   sudo ip route add default via 192.168.14.1 dev ens33")


if __name__ == "__main__":
    main()