import json
import hashlib
import hmac
import time
import urllib.parse

# 配置环境变量（密钥、区域等）)X-APP-ID对应账号信息中的ID值，X-APP-KEY对应账号信息中的KEY值
X_APP_ID = '97316fce99ea440dadf4c10864220ae9'
X_APP_KEY = '285d8ca376fa46fb8972e5ac9cc0801b'

# URL 和请求数据
REGION = 'QG'
EXPIRATION_IN_SECONDS = '43200'  # 默认过期时间,这里配置12小时
TIMESTAMP = str(int(time.time()))  # 当前时间戳
SIGNED_HEADERS = 'x-app-id'  # 默认签名头
PUBLIC_NETWORK_SING_HEADER = 'teleai-cloud-auth-v1'  # 公网鉴权头部，按照实际调用情况选择
# EMS_SING_HEADER = 'eop-auth-v1'  # 内网鉴权头部，按照实际调用情况选择

# 构建请求头
headers = {
    'Content-Type': 'application/json',
    'X-APP-ID': X_APP_ID,
}


class HttpAuth(object):
    # 编码函数
    def normalize(self, string, encoding_slash=True):
        quoted_string = urllib.parse.quote(string, safe='~()*!\'/' if encoding_slash else '~()*!\'')
        return quoted_string

    # 生成Canonical URI
    def generate_canonical_uri(self, url):
        parsed_url = urllib.parse.urlparse(url)
        return '/'.join(self.normalize(segment, False) for segment in parsed_url.path.split('/'))

    # 生成Canonical Headers
    @staticmethod
    def generate_canonical_headers(input_params):
        signed_headers_list = SIGNED_HEADERS.split(';')
        signed_headers_set = set(signed_headers_list)
        sorted_headers = sorted((k.lower(), urllib.parse.quote(v.strip(), safe='')) for k, v in input_params.items() if
                                k.lower() in signed_headers_set)
        canonical_headers = ''.join(f"{k}:{v}" for k, v in sorted_headers)
        signed_headers_str = ';'.join(sorted(signed_headers_set))
        print("canonical_headers:", canonical_headers)
        return canonical_headers, signed_headers_str

    # 生成签名
    def generate_signature(self, x_app_id, x_app_key, region, timestamp, expiration_in_seconds, method,
                           canonical_uri,
                           canonical_headers, signed_headers_str, canonical_query_string):
		# 在此处选择对应的鉴权头部
        signing_key_str = f"{PUBLIC_NETWORK_SING_HEADER}/{x_app_id}/{region}/{timestamp}/{expiration_in_seconds}"

        signing_key = hmac.new(bytes(x_app_key, 'utf-8'), bytes(signing_key_str, 'utf-8'), hashlib.sha256).hexdigest()

        # print(f"signing_key = {signing_key}")
        canonical_request = f"{method.upper()}\n{canonical_uri}\n{canonical_query_string}\n{canonical_headers}"
        print("canonical_request", canonical_request)
        signature = hmac.new(bytes(signing_key, 'utf-8'), bytes(canonical_request, 'utf-8'), hashlib.sha256).hexdigest()
        authorization = f"{signing_key_str}/{signed_headers_str}/{signature}"
        # print("authorization", authorization)
        return authorization

    # 获取Content-Length
    def get_content_length(self, data):
        body = json.dumps(data)
        return str(len(body))

    # 发送请求并获取响应
    def get_auth(self, url, method, canonical_query_string):
        """
		主逻辑

		:param url: 完整的请求url
		:param method: GET/POST，根据实际情况传入，websocket请求传GET
		:param canonical_query_string: params参数，GET请求需要传入，格式为key=value，其他请求请传入''
		"""
        canonical_uri = self.generate_canonical_uri(url)

        canonical_headers, signed_headers_str = self.generate_canonical_headers(headers)
        authorization = self.generate_signature(X_APP_ID, X_APP_KEY, REGION, TIMESTAMP, EXPIRATION_IN_SECONDS,
                                                method, canonical_uri, canonical_headers, signed_headers_str, canonical_query_string)
        headers['Authorization'] = authorization
        print(f"authorization = {authorization}")
        return headers


# getAuth = HttpAuth().get_auth("111", "GET", 'a=1')