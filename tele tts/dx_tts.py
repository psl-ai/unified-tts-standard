import logging
import time
from datetime import datetime

import requests
from SignUtils import HttpAuth

import base64
import re





# URL 和请求数据
url = "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/supernatural"  # 请求的URL
# url = "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/offLineSynthesis"  # 请求的URL

AuthInfo = HttpAuth().get_auth(url, "POST", '')

print(AuthInfo)

# 配置日志，设置日志级别为INFO，并指定日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 配置环境变量
X_APP_ID = "97316fce99ea440dadf4c10864220ae9"


AUTHORIZATION = AuthInfo.get('Authorization')


request_data = {
    "timestamp": int(time.time()),
    "req_id": "test001",
    "text": "将短音频（≤60秒）精准识别成文字，除中文普通话和英文外，支持65个语种、23种方言和1个民族语言，实时返回结果，达到边说边返回的效果，可提供公有云接口及私有化部署方案",
    "format": "WAV",
    "voice": "xianliaonv",
}

# 构建请求头
headers = {
    "Content-Type": "application/json",
    "X-APP-ID": X_APP_ID,
    "Authorization": AUTHORIZATION
}


def timeSimple(timestamp):
    # 将时间戳转换为HH:MM:SS格式的时间字符串
    dt_object = datetime.fromtimestamp(timestamp)
    formatted_time = dt_object.strftime("%H:%M:%S")
    return formatted_time


def send_request(url):
    try:
        start_time = time.time()
        logging.info(f"请求路径: {url}")
        logging.info(f"开始发送: {timeSimple(start_time)}")

        with requests.post(
            url, json=request_data, headers=headers, stream=True, verify=False
        ) as response:
            first_packet_time = None
            if response.status_code == 200:
                logging.info(f"接受到返回: {timeSimple(time.time())}")

                # print(response.json()['result']['audio'])

                mp3_data = base64.b64decode(response.json()['result']['audio'])

                # 2. 以二进制写入模式打开本地文件并保存
                with open("output.wav", "wb") as f:
                    f.write(mp3_data)

                print("MP3 文件已保存为 output.mp3")

                # all_base64 = ""
                # for chunk in response.iter_content(chunk_size=1024):
                #     if chunk:
                #         if first_packet_time is None:
                #             first_packet_time = time.time()
                #         logging.info(
                #             f"Received chunk: {timeSimple(time.time())} {chunk.decode('utf-8')}"
                #         )
                #         all_base64 = all_base64 + chunk.decode('utf-8')
                # print(len(all_base64))
                # if all_base64:
                #     save_audio(all_base64, "my_sound.mp3")
                # end_time = time.time()
                # logging.info(f"Time to first byte (TTFB): {first_packet_time - start_time:.3f} seconds")
                # logging.info(f"Request completed in {end_time - start_time:.3f} seconds")
            else:
                logging.error(f"Request failed with status code {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")


# 发送请求
send_request(url)
logging.info(f"headers = {headers}")