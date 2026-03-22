import time
import sys
import json

import requests
from loguru import logger
from utils.xianyu_utils import generate_sign


class XianyuApis:
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.url = 'https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/'
        self.session = requests.Session()
        self.session.headers.update({
            'accept': 'application/json',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': 'https://www.goofish.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.goofish.com/',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        })

    def clear_duplicate_cookies(self):
        """清理重复的cookies"""
        new_jar = requests.cookies.RequestsCookieJar()
        added_cookies = set()
        cookie_list = list(self.session.cookies)
        cookie_list.reverse()
        for cookie in cookie_list:
            if cookie.name not in added_cookies:
                new_jar.set_cookie(cookie)
                added_cookies.add(cookie.name)
        self.session.cookies = new_jar
        self.update_env_cookies()

    def update_env_cookies(self):
        """更新 Cookie 存储到数据库"""
        try:
            cookie_str = '; '.join([f"{c.name}={c.value}" for c in self.session.cookies])
            if self.config_manager:
                self.config_manager.update_cookies(cookie_str)
        except Exception as e:
            logger.warning(f"更新Cookie存储失败: {str(e)}")

    def hasLogin(self, retry_count=0):
        """调用hasLogin.do接口进行登录状态检查"""
        if retry_count >= 2:
            logger.error("Login检查失败，重试次数过多")
            return False

        try:
            url = 'https://passport.goofish.com/newlogin/hasLogin.do'
            params = {
                'appName': 'xianyu',
                'fromSite': '77'
            }
            data = {
                'hid': self.session.cookies.get('unb', ''),
                'ltl': 'true',
                'appName': 'xianyu',
                'appEntrance': 'web',
                '_csrf_token': self.session.cookies.get('XSRF-TOKEN', ''),
                'umidToken': '',
                'hsiz': self.session.cookies.get('cookie2', ''),
                'bizParams': 'taobaoBizLoginFrom=web',
                'mainPage': 'false',
                'isMobile': 'false',
                'lang': 'zh_CN',
                'returnUrl': '',
                'fromSite': '77',
                'isIframe': 'true',
                'documentReferer': 'https://www.goofish.com/',
                'defaultView': 'hasLogin',
                'umidTag': 'SERVER',
                'deviceId': self.session.cookies.get('cna', '')
            }

            response = self.session.post(url, params=params, data=data)
            res_json = response.json()

            if res_json.get('content', {}).get('success'):
                logger.debug("Login成功")
                self.clear_duplicate_cookies()
                return True
            else:
                logger.warning(f"Login失败: {res_json}")
                time.sleep(0.5)
                return self.hasLogin(retry_count + 1)

        except Exception as e:
            logger.error(f"Login请求异常: {str(e)}")
            time.sleep(0.5)
            return self.hasLogin(retry_count + 1)

    @staticmethod
    def check_login_status(cookies_str: str) -> tuple:
        """
        检查登录状态。
        先快检 cookies_str 是否含非空 unb 字段，
        再实例化临时 XianyuApis 发 HTTP 请求验证。
        返回 (True, "") 或 (False, "")。
        """
        # 快检：解析 cookie 字符串，查找 unb（使用精确匹配）
        unb = ""
        for part in cookies_str.split(";"):
            part = part.strip()
            if "=" in part:
                key, val = part.split("=", 1)
                if key.strip() == "unb" and val.strip():
                    unb = val.strip()
                    break
        if not unb:
            logger.debug("快检失败：未找到 unb 字段")
            return False, ""

        # HTTP 验证
        try:
            api = XianyuApis()
            # 将 cookies_str 加载到 session
            from http.cookies import SimpleCookie
            cookie = SimpleCookie()
            cookie.load(cookies_str)
            for key, morsel in cookie.items():
                api.session.cookies.set(key, morsel.value, domain='.goofish.com')

            # Inline HTTP check with explicit timeout (bypasses hasLogin retry logic)
            url = 'https://passport.goofish.com/newlogin/hasLogin.do'
            params = {'appName': 'xianyu', 'fromSite': '77'}
            data = {
                'hid': api.session.cookies.get('unb', ''),
                'ltl': 'true',
                'appName': 'xianyu',
                'appEntrance': 'web',
                '_csrf_token': api.session.cookies.get('XSRF-TOKEN', ''),
                'umidToken': '',
                'hsiz': api.session.cookies.get('cookie2', ''),
                'bizParams': 'taobaoBizLoginFrom=web',
                'mainPage': 'false',
                'isMobile': 'false',
                'lang': 'zh_CN',
                'returnUrl': '',
                'fromSite': '77',
                'isIframe': 'true',
                'documentReferer': 'https://www.goofish.com/',
                'defaultView': 'hasLogin',
                'umidTag': 'SERVER',
                'deviceId': api.session.cookies.get('cna', ''),
            }
            response = api.session.post(url, params=params, data=data, timeout=5)
            res_json = response.json()
            ok = bool(res_json.get('content', {}).get('success'))
            return ok, ""
        except Exception as e:
            logger.warning(f"登录状态 HTTP 验证异常: {e}")
            return False, ""

    def get_token(self, device_id, retry_count=0):
        if retry_count >= 2:
            logger.warning("获取token失败，尝试重新登陆")
            if self.hasLogin():
                logger.info("重新登录成功，重新尝试获取token")
                return self.get_token(device_id, 0)
            else:
                logger.error("重新登录失败，Cookie已失效")
                print(json.dumps({
                    "type": "error",
                    "code": "COOKIE_EXPIRED",
                    "message": "Cookie已失效，请在设置页面更新Cookie后重新启动机器人"
                }, ensure_ascii=False), flush=True)
                sys.exit(1)

        params = {
            'jsv': '2.7.2',
            'appKey': '34839810',
            't': str(int(time.time()) * 1000),
            'sign': '',
            'v': '1.0',
            'type': 'originaljson',
            'accountSite': 'xianyu',
            'dataType': 'json',
            'timeout': '20000',
            'api': 'mtop.taobao.idlemessage.pc.login.token',
            'sessionOption': 'AutoLoginOnly',
            'spm_cnt': 'a21ybx.im.0.0',
        }
        data_val = '{"appKey":"444e9908a51d1cb236a27862abc769c9","deviceId":"' + device_id + '"}'
        data = {
            'data': data_val,
        }

        token = self.session.cookies.get('_m_h5_tk', '').split('_')[0]
        sign = generate_sign(params['t'], token, data_val)
        params['sign'] = sign

        try:
            response = self.session.post(
                'https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/',
                params=params,
                data=data
            )
            res_json = response.json()

            if isinstance(res_json, dict):
                ret_value = res_json.get('ret', [])
                if not any('SUCCESS::调用成功' in ret for ret in ret_value):
                    error_msg = str(ret_value)
                    if 'RGV587_ERROR' in error_msg or '被挤爆啦' in error_msg:
                        logger.error(f"触发风控: {ret_value}")
                        print(json.dumps({
                            "type": "error",
                            "code": "WIND_CONTROL",
                            "message": "触发风控，请在设置页面更新Cookie后重新启动机器人"
                        }, ensure_ascii=False), flush=True)
                        sys.exit(1)

                    logger.warning(f"Token API调用失败，错误信息: {ret_value}")
                    if 'Set-Cookie' in response.headers:
                        logger.debug("检测到Set-Cookie，更新cookie")
                        self.clear_duplicate_cookies()
                    time.sleep(0.5)
                    return self.get_token(device_id, retry_count + 1)
                else:
                    logger.info("Token获取成功")
                    return res_json
            else:
                logger.error(f"Token API返回格式异常: {res_json}")
                return self.get_token(device_id, retry_count + 1)

        except Exception as e:
            logger.error(f"Token API请求异常: {str(e)}")
            time.sleep(0.5)
            return self.get_token(device_id, retry_count + 1)

    def get_item_info(self, item_id, retry_count=0):
        """获取商品信息，自动处理token失效的情况"""
        if retry_count >= 3:
            logger.error("获取商品信息失败，重试次数过多")
            return {"error": "获取商品信息失败，重试次数过多"}

        params = {
            'jsv': '2.7.2',
            'appKey': '34839810',
            't': str(int(time.time()) * 1000),
            'sign': '',
            'v': '1.0',
            'type': 'originaljson',
            'accountSite': 'xianyu',
            'dataType': 'json',
            'timeout': '20000',
            'api': 'mtop.taobao.idle.pc.detail',
            'sessionOption': 'AutoLoginOnly',
            'spm_cnt': 'a21ybx.im.0.0',
        }

        data_val = '{"itemId":"' + item_id + '"}'
        data = {
            'data': data_val,
        }

        token = self.session.cookies.get('_m_h5_tk', '').split('_')[0]
        sign = generate_sign(params['t'], token, data_val)
        params['sign'] = sign

        try:
            response = self.session.post(
                'https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/',
                params=params,
                data=data
            )

            res_json = response.json()
            if isinstance(res_json, dict):
                ret_value = res_json.get('ret', [])
                if not any('SUCCESS::调用成功' in ret for ret in ret_value):
                    logger.warning(f"商品信息API调用失败，错误信息: {ret_value}")
                    if 'Set-Cookie' in response.headers:
                        logger.debug("检测到Set-Cookie，更新cookie")
                        self.clear_duplicate_cookies()
                    time.sleep(0.5)
                    return self.get_item_info(item_id, retry_count + 1)
                else:
                    logger.debug(f"商品信息获取成功: {item_id}")
                    return res_json
            else:
                logger.error(f"商品信息API返回格式异常: {res_json}")
                return self.get_item_info(item_id, retry_count + 1)

        except Exception as e:
            logger.error(f"商品信息API请求异常: {str(e)}")
            time.sleep(0.5)
            return self.get_item_info(item_id, retry_count + 1)
