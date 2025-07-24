#!/usr/bin/env python3
"""
启动AI2-THOR Web Demo的简单脚本
检查依赖并启动Web应用
"""

import sys
import os

def check_dependencies():
    """检查必要的依赖"""
    required_packages = ['flask', 'flask_socketio', 'ai2thor', 'cv2', 'numpy']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'cv2':
                import cv2
                # Mark as used
                _ = cv2
            elif package == 'flask_socketio':
                import flask_socketio
                # Mark as used  
                _ = flask_socketio
            else:
                __import__(package)
            print(f"✓ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} 未安装")
    
    return missing_packages

def check_data_engine():
    """检查data_engine目录和RocAgent"""
    try:
        sys.path.append('data_engine')
        from RocAgent import RocAgent
        # Mark as used
        _ = RocAgent
        print("✓ RocAgent 导入成功")
        return True
    except ImportError as e:
        print(f"✗ RocAgent 导入失败: {e}")
        return False

def main():
    print("=" * 50)
    print("AI2-THOR Web Demo 启动检查")
    print("=" * 50)
    
    # 检查当前目录
    if not os.path.exists('data_engine'):
        print("✗ 当前目录中找不到data_engine文件夹")
        print("请确保在项目根目录运行此脚本")
        return 1
    
    # 检查依赖
    print("\n检查Python依赖...")
    missing_packages = check_dependencies()
    
    if missing_packages:
        print(f"\n缺少依赖包: {', '.join(missing_packages)}")
        print("请运行以下命令安装:")
        if 'flask_socketio' in missing_packages:
            print("pip install flask flask-socketio")
        if 'cv2' in missing_packages:
            print("pip install opencv-python")
        if 'ai2thor' in missing_packages:
            print("pip install ai2thor")
        return 1
    
    # 检查data_engine
    print("\n检查项目结构...")
    if not check_data_engine():
        return 1
    
    # 启动Web应用
    print("\n" + "=" * 50)
    print("所有检查通过! 正在启动Web应用...")
    print("=" * 50)
    print()
    print("🌐 Web应用将在以下地址启动:")
    print("   http://localhost:5001")
    print()
    print("📋 使用说明:")
    print("   1. 在浏览器中打开上述地址")
    print("   2. 选择场景并点击'初始化环境'")
    print("   3. 使用键盘或按钮控制代理人移动")
    print()
    print("⌨️  键盘控制:")
    print("   WASD - 移动 | QE - 转向 | RF - 视角")
    print("   空格 - 拾取 | X - 放下 | C - 交互")
    print()
    print("💡 提示: 如果端口5001被占用，程序会自动尝试其他端口")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    print()
    
    try:
        # 导入并运行web应用
        from web_app import app, socketio
        
        # 尝试不同端口
        ports = [5001, 5002, 5003, 8000, 8080]
        for port in ports:
            try:
                print(f"尝试在端口 {port} 启动服务器...")
                socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
                break
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"端口 {port} 已被占用，尝试下一个端口...")
                    continue
                else:
                    raise e
        else:
            print("所有端口都被占用，无法启动服务器")
            return 1
    except KeyboardInterrupt:
        print("\n\n🛑 Web应用已停止")
        return 0
    except Exception as e:
        print(f"\n❌ 启动Web应用时出错: {e}")
        return 1

if __name__ == "__main__":
    exit(main())