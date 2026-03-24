import hashlib

import requests
import json
from typing import Dict, Any, Optional, Union
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from urllib.parse import urljoin
import time


def md5_encrypt(password: str) -> str:
    """
    将密码转换为MD5加密字符串

    Args:
        password: 原始密码字符串

    Returns:
        str: 32位小写MD5加密字符串
    """
    # 创建md5对象
    md5 = hashlib.md5()

    # 对密码进行编码并更新md5对象
    md5.update(password.encode('utf-8'))

    # 获取16进制加密结果
    return md5.hexdigest()


class APIManager(QObject):
    """HTTP接口管理器 - 自动处理SessionID和Cookie"""

    # 信号定义
    login_success = pyqtSignal(dict)  # 登录成功，传递用户信息
    login_failed = pyqtSignal(str)  # 登录失败，传递错误信息
    request_success = pyqtSignal(str, dict)  # 请求成功，(接口名, 响应数据)
    request_failed = pyqtSignal(str, str)  # 请求失败，(接口名, 错误信息)
    session_expired = pyqtSignal()  # Session过期信号

    def __init__(self, base_url: str = "", parent=None):
        """
        初始化API管理器

        Args:
            base_url: API基础URL，例如 "http://api.example.com/v1/"
            parent: 父对象
        """
        super().__init__(parent)
        self.base_url = base_url.rstrip('/') + '/' if base_url else ""
        self.session = requests.Session()
        self.session_id = None
        self.user_name = None
        self.is_logged_in = False

        # 请求头配置
        self.headers = {

            'Content-Type': 'application/json',
            'Accept': 'text/html, application/xhtml+xml, */*'
        }
        # Accept: text / html, application / xhtml + xml, * / *
        # Content - Type: application / json
        # Cookie: sessionId = 760904f8 - 0440 - 4355 - 9bb1 - c4a4c63e0603

        # 超时配置
        self.timeout = 30

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1  # 秒

    def set_base_url(self, base_url: str):
        """设置基础URL"""
        self.base_url = base_url.rstrip('/') + '/' if base_url else ""

    def build_url(self, endpoint: str) -> str:
        """构建完整的URL"""
        if self.base_url and not endpoint.startswith(('http://', 'https://')):
            return urljoin(self.base_url, endpoint.lstrip('/'))
        return endpoint

    def update_headers(self, headers: Dict[str, str] = None):
        """更新请求头"""
        if headers:
            self.headers.update(headers)

    def get_session_id(self) -> Optional[str]:
        """获取当前的Session ID"""
        if self.session_id:
            return self.session_id

        # 从Cookie中获取
        if 'sessionId' in self.session.cookies.get_dict():
            self.session_id = self.session.cookies.get('sessionId')
            return self.session_id

        return None

    def login(self, login_url: str, username: str, password: str,
              extra_data: Dict[str, Any] = None) -> bool:
        """
        登录接口，获取Session ID

        Args:
            login_url: 登录接口URL（相对或绝对）
            username: 用户名
            password: 密码
            extra_data: 额外的登录参数

        Returns:
            bool: 是否登录成功
        """
        try:
            # 准备登录数据
            login_data = {
                'accounter': username,
                'password': md5_encrypt(password)
            }

            if extra_data:
                login_data.update(extra_data)

            # 发送登录请求
            full_url = self.build_url(login_url)
            response = self.session.get(
                full_url,
                params=login_data,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                # 尝试解析响应数据
                try:
                    data = response.json().get('data')
                    print(data)

                    # 检查响应中是否有sessionId
                    if 'sessionId' in data:
                        self.session_id = data['sessionId']
                    # # 或者从Cookie中获取
                    # elif 'sessionId' in response.cookies:
                    #     self.session_id = response.cookies.get('sessionId')

                    # 保存用户信息
                    self.user_name = data.get('userName', {})
                    self.is_logged_in = True

                    # 发出登录成功信号
                    self.login_success.emit({
                        'session_id': self.session_id,
                        'user_name': self.user_name,
                        'headers': dict(response.headers),
                        'cookies': dict(response.cookies)
                    })

                    print(f"登录成功: {username}")
                    return True

                except json.JSONDecodeError:
                    # 如果不是JSON响应，检查Cookie
                    if 'sessionId' in response.cookies:
                        self.session_id = response.cookies.get('sessionId')
                        self.is_logged_in = True

                        self.login_success.emit({
                            'session_id': self.session_id,
                            'headers': dict(response.headers),
                            'cookies': dict(response.cookies)
                        })

                        print(f"登录成功: {username}")
                        return True

            # 登录失败
            error_msg = f"登录失败: {response.status_code} - {response.text}"
            self.login_failed.emit(error_msg)
            print(error_msg)
            return False

        except requests.exceptions.RequestException as e:
            error_msg = f"登录请求异常: {str(e)}"
            self.login_failed.emit(error_msg)
            print(error_msg)
            return False

    def get(self, endpoint: str, params: Dict[str, Any] = None,
            headers: Dict[str, str] = None,
            api_name: str = "GET请求") -> Optional[Dict[str, Any]]:
        """
        发送GET请求（同步）

        Args:
            endpoint: API端点
            params: 查询参数
            headers: 额外的请求头
            api_name: API名称，用于信号传递

        Returns:
            Optional[Dict]: 响应数据，失败返回None
        """
        try:
            # 检查登录状态
            if not self.is_logged_in :
                print("警告: 未登录状态发送请求")

            # 准备请求
            full_url = self.build_url(endpoint)
            request_headers = self.headers.copy()
            print(f"headers: {request_headers}")
            # 添加Session ID到请求头（如果需要）
            session_id = self.get_session_id()
            if session_id:
                request_headers['Cookie'] = f'sessionId = {session_id}'

            # 发送请求（带重试机制）
            response = None
            for attempt in range(self.max_retries):
                try:
                    # self.session.cookies.set("sessionId", session_id)
                    cookies = {'sessionId': session_id}
                    response = self.session.get(
                        full_url,
                        params=params,
                        headers=request_headers,
                        timeout=self.timeout,
                    )
                    break
                except requests.exceptions.Timeout:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        raise

            # 检查响应状态
            if response.status_code == 200:
                try:
                    data = response.json().get('data')
                    print(f"data: {data}")
                   # self.request_success.emit(api_name, data)
                    return data
                except json.JSONDecodeError:
                    # 如果不是JSON，返回文本
                    data = {'text': response.text}
                    self.request_success.emit(api_name, data)
                    return data

            elif response.status_code == 401:
                # Session过期
                self.is_logged_in = False
                self.session_expired.emit()
                error_msg = f"{api_name}: Session已过期"
                self.request_failed.emit(api_name, error_msg)
                print(f"")

            else:
                error_msg = f"{api_name}失败: {response.status_code} - {response.text}"
                self.request_failed.emit(api_name, error_msg)
                print(error_msg)

            return None

        except requests.exceptions.RequestException as e:
            error_msg = f"{api_name}请求异常: {str(e)}"
            self.request_failed.emit(api_name, error_msg)
            print(error_msg)
            return None

    def post(self, endpoint: str, data: Dict[str, Any] = None,
             params: Dict[str, Any] = None,
             headers: Dict[str, str] = None,
             api_name: str = "POST请求") -> Optional[Dict[str, Any]]:
        """
        发送POST请求（同步）

        Args:
            endpoint: API端点
            data: POST数据
            params: 查询参数
            headers: 额外的请求头
            api_name: API名称，用于信号传递

        Returns:
            Optional[Dict]: 响应数据，失败返回None
        """
        try:
            # 检查登录状态
            if not self.is_logged_in and endpoint != "/login":
                print("警告: 未登录状态发送请求")

            # 准备请求
            full_url = self.build_url(endpoint)
            request_headers = self.headers.copy()

            # 添加Session ID到请求头
            session_id = self.get_session_id()
            if session_id:
                request_headers['Cookie'] = f'sessionId={session_id}'

            # 添加自定义请求头
            if headers:
                request_headers.update(headers)

            # 发送请求（带重试机制）
            response = None
            for attempt in range(self.max_retries):
                try:
                    response = self.session.post(
                        full_url,
                        json=data,
                        params=params,
                        headers=request_headers,
                        timeout=self.timeout
                    )
                    break
                except requests.exceptions.Timeout:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        raise

            # 检查响应状态
            if response.status_code == 200:
                try:
                    result = response.json()
                    self.request_success.emit(api_name, result)
                    return result
                except json.JSONDecodeError:
                    result = {'text': response.text}
                    self.request_success.emit(api_name, result)
                    return result

            elif response.status_code == 401:
                # Session过期
                self.is_logged_in = False
                self.session_expired.emit()
                error_msg = f"{api_name}: Session已过期"
                self.request_failed.emit(api_name, error_msg)
                print(error_msg)

            else:
                error_msg = f"{api_name}失败: {response.status_code} - {response.text}"
                self.request_failed.emit(api_name, error_msg)
                print(error_msg)

            return None

        except requests.exceptions.RequestException as e:
            error_msg = f"{api_name}请求异常: {str(e)}"
            self.request_failed.emit(api_name, error_msg)
            print(error_msg)
            return None

    def put(self, endpoint: str, data: Dict[str, Any] = None,
            headers: Dict[str, str] = None,
            api_name: str = "PUT请求") -> Optional[Dict[str, Any]]:
        """发送PUT请求"""
        try:
            full_url = self.build_url(endpoint)
            request_headers = self.headers.copy()

            session_id = self.get_session_id()
            if session_id:
                request_headers['Cookie'] = f'sessionId={session_id}'

            if headers:
                request_headers.update(headers)

            response = self.session.put(
                full_url,
                json=data,
                headers=request_headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                self.request_success.emit(api_name, result)
                return result
            else:
                error_msg = f"{api_name}失败: {response.status_code}"
                self.request_failed.emit(api_name, error_msg)
                return None

        except requests.exceptions.RequestException as e:
            error_msg = f"{api_name}请求异常: {str(e)}"
            self.request_failed.emit(api_name, error_msg)
            return None

    def delete(self, endpoint: str, headers: Dict[str, str] = None,
               api_name: str = "DELETE请求") -> Optional[Dict[str, Any]]:
        """发送DELETE请求"""
        try:
            full_url = self.build_url(endpoint)
            request_headers = self.headers.copy()

            session_id = self.get_session_id()
            if session_id:
                request_headers['Cookie'] = f'sessionId={session_id}'

            if headers:
                request_headers.update(headers)

            response = self.session.delete(
                full_url,
                headers=request_headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                self.request_success.emit(api_name, result)
                return result
            else:
                error_msg = f"{api_name}失败: {response.status_code}"
                self.request_failed.emit(api_name, error_msg)
                return None

        except requests.exceptions.RequestException as e:
            error_msg = f"{api_name}请求异常: {str(e)}"
            self.request_failed.emit(api_name, error_msg)
            return None

    def logout(self, logout_url: str = "/logout") -> bool:
        """
        退出登录

        Args:
            logout_url: 退出登录接口URL

        Returns:
            bool: 是否退出成功
        """
        try:
            response = self.get(logout_url, api_name="退出登录")

            # 清除会话信息
            self.session_id = None
            self.user_name = None
            self.is_logged_in = False
            self.session.cookies.clear()

            print("已退出登录")
            return True

        except Exception as e:
            print(f"退出登录异常: {e}")
            return False

    def check_session(self, check_url: str = "/check_session") -> bool:
        """
        检查Session是否有效

        Args:
            check_url: 检查Session的接口URL

        Returns:
            bool: Session是否有效
        """
        try:
            response = self.get(check_url, api_name="检查Session")
            return response is not None and 'valid' in response
        except:
            return False

    def get_cookies(self) -> Dict[str, str]:
        """获取所有Cookie"""
        return dict(self.session.cookies)

    def set_cookie(self, name: str, value: str):
        """设置Cookie"""
        self.session.cookies.set(name, value)

    def clear_cookies(self):
        """清除所有Cookie"""
        self.session.cookies.clear()

    def __del__(self):
        """析构函数"""
        if self.session:
            self.session.close()




class APIService:
    """API服务 - 组合API管理器和配置"""

    def __init__(self, base_url):
        self.api_manager = APIManager(base_url)

        # 连接信号
        self.api_manager.login_success.connect(self.on_login_success)
        self.api_manager.login_failed.connect(self.on_login_failed)
        self.api_manager.request_success.connect(self.on_request_success)
        self.api_manager.request_failed.connect(self.on_request_failed)
        self.api_manager.session_expired.connect(self.on_session_expired)


    def login(self, username: str, password: str) -> bool:
        """登录"""
        return self.api_manager.login('/api/User/Login',username,password)



# 定义具体想要用的接口
    def call_api(self, api_name: str, data: Dict[str, Any] = None,
                 params: Dict[str, Any] = None,
                 headers: Dict[str, str] = None) -> Optional[Dict[str, Any]]:
        """调用API"""
        endpoint = self.config.get_endpoint(api_name)
        if not endpoint:
            print(f"未找到API: {api_name}")
            return None

        method = endpoint['method']

        if method == 'GET':
            return self.api_manager.get(
                endpoint['url'],
                params=params,
                headers=headers,
                api_name=api_name
            )
        elif method == 'POST':
            return self.api_manager.post(
                endpoint['url'],
                data=data,
                params=params,
                headers=headers,
                api_name=api_name
            )
        elif method == 'PUT':
            return self.api_manager.put(
                endpoint['url'],
                data=data,
                headers=headers,
                api_name=api_name
            )
        elif method == 'DELETE':
            return self.api_manager.delete(
                endpoint['url'],
                headers=headers,
                api_name=api_name
            )
        else:
            print(f"不支持的HTTP方法: {method}")
            return None

    # 信号处理方法
    def on_login_success(self, user_name: dict):
        print(f"登录成功: {user_name}")

    def on_login_failed(self, error_msg: str):
        print(f"登录失败: {error_msg}")

    def on_request_success(self, api_name: str, data: dict):
        print(f"{api_name} 请求成功")

    def on_request_failed(self, api_name: str, error_msg: str):
        print(f"{api_name} 请求失败: {error_msg}")

    def on_session_expired(self):
        print("Session已过期，请重新登录")

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self.api_manager.is_logged_in

    def get_session_id(self) -> Optional[str]:
        """获取Session ID"""
        return self.api_manager.get_session_id()

    def getUserList(self):
        return self.api_manager.get(
            '/api/User/GetUserList',
            None
        )

    def getDepartmentsList(self):
        return self.api_manager.get(
            '/api/Department/GetDepartmentList',
            None
        )

    def getMqttAdr(self):
        return self.api_manager.get("/api/Web/getMqttAdr")

    def getAllReaches(self):
        return self.api_manager.get("/api/Web/getAllReachs")

    def getFencesAll(self):
        return self.api_manager.get("/api/Web/getFencesAll")

    def getLedInfoAll(self,reachCode):
        return self.api_manager.get("/api/Device/GetLEDInforList",{"REACHCODE":reachCode})

    def getLoraInforList(self,reachCode):
        return self.api_manager.get('/api/Device/GetLoRaInforList',{"REACHCODE":reachCode})

    def getReachTopics(self,reachCode):
        return self.api_manager.get("/api/Device/GetReachTopics",{"REACHCODE":reachCode})

    def get_ship_name(self,mmsi):
        data= {}
        # data= self.api_manager.get("/api/Ship/GetShipName", {"MMSI": mmsi})
        return data.get("ShipName","")  if data else ""

# ========== 使用示例 ==========
if __name__ == "__main__":
    api=APIService("http://isc.cqu.edu.cn:23456")
    arr=api.login("梁山", "Cqhdj@2024")
    print(arr)
    print(api.get_session_id())
    users=api.getAllReaches()
    print(users)