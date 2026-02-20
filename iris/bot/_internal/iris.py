from dataclasses import dataclass
import json
import requests
import typing as t
import base64
import os # 추가됨
from io import BufferedIOBase, BytesIO, BufferedReader
from PIL import Image
from urllib.parse import urlparse, unquote

@dataclass
class IrisRequest:
    msg: str
    room: str
    sender: str
    raw: dict
    
class IrisAPI:
    def __init__(self, iris_endpoint: str):
        self.iris_endpoint = iris_endpoint

    def __parse(self, res: requests.Response) -> dict:
        try:
            data: dict = res.json()
        except Exception:
            raise Exception(f"Iris 응답 JSON 파싱 오류: {res.text}")

        if not 200 <= res.status_code <= 299:
            print(f"Iris 오류: {res}")
            raise Exception(f"Iris 오류: {data.get('message', '알 수 없는 오류')}")

        return data

    def reply(self, room_id: int, msg: str, thread_id: int | None = None):
        json_data = {"type": "text", "room": str(room_id), "data": str(msg)}
        if thread_id is not None:
            json_data["threadId"] = str(thread_id)
        res = requests.post(
            f"{self.iris_endpoint}/reply",
            json=json_data,
        )
        return self.__parse(res)

    def reply_media(
        self,
        room_id: int,
        files: t.List[BufferedIOBase | bytes | Image.Image | str],
        thread_id: int | None = None,
    ):
        if type(files) is not list:
            files = [files]
        data = []
        for file in files:
            try:
                if isinstance(file, BufferedIOBase):
                    data.append(base64.b64encode(file.read()).decode())
                elif isinstance(file, bytes):
                    data.append(base64.b64encode(file).decode())
                elif isinstance(file, Image.Image):
                    image_bytes_io = BytesIO()
                    img = file.convert("RGBA")
                    img.save(image_bytes_io, format="PNG")
                    image_bytes_io.seek(0)
                    buffered_reader = BufferedReader(image_bytes_io)
                    data.append(base64.b64encode(buffered_reader.read()).decode())
                elif isinstance(file, str):
                    try:
                        if file.startswith("http"):
                            res = requests.get(file)
                            if res.status_code == 200:
                                file = res.content
                            else:
                                print(f"이미지 다운로드 실패: {res.status_code}")
                        else:
                            with open(file, "rb") as f:
                                file = f.read()
                        data.append(base64.b64encode(file).decode())
                    except Exception as e:
                        print(f"이미지 처리 중 오류 발생: {e}")
                else:
                    print(f"지원하지 않는 형식입니다: {type(file)}")
            except TypeError as e:
                print(f"이미지 처리 중 오류 발생: {e}")
                continue
        if len(data) > 0:
            json_data = {"type": "image_multiple", "room": str(room_id), "data": data}
            if thread_id is not None:
                json_data["threadId"] = str(thread_id)
            res = requests.post(
                f"{self.iris_endpoint}/reply",
                json=json_data,
            )
            return self.__parse(res)
        else:
            print("이미지 전송이 모두 실패하였습니다. 이미지 전송 요청 부분을 확인해주세요.")

    def decrypt(self, enc: int, b64_ciphertext: str, user_id: int) -> str | None:
        res = requests.post(
            f"{self.iris_endpoint}/decrypt",
            json={"enc": enc, "b64_ciphertext": b64_ciphertext, "user_id": user_id},
        )

        res = self.__parse(res)
        return res.get("plain_text")

    def query(self, query: str, bind: list[t.Any] | None = None) -> list[dict]:
        res = requests.post(
            f"{self.iris_endpoint}/query", json={"query": query, "bind": bind or []}
        )
        res = self.__parse(res)
        return res.get("data", [])

    def get_info(self):
        res = requests.get(f"{self.iris_endpoint}/config")
        return self.__parse(res)

    def get_aot(self):
        res = requests.get(f"{self.iris_endpoint}/aot")
        return self.__parse(res)

    # 추가됨
    def reply_audio(
        self,
        room_id: int,
        files: t.List[BufferedIOBase | bytes | str],
        thread_id: int | None = None,
    ):
        if type(files) is not list:
            files = [files]
        data = []
        for idx, file in enumerate(files):
            try:
                if isinstance(file, BufferedIOBase):
                    name = getattr(file, "name", None)
                    filename = (
                        os.path.basename(str(name))
                        if name
                        else f"audio_{idx}.mp3"
                    )
                    data.append(
                        ("file", (filename, file.read(), "application/octet-stream"))
                    )
                elif isinstance(file, bytes):
                    data.append(
                        (
                            "file",
                            (
                                f"audio_{idx}.mp3",
                                file,
                                "application/octet-stream",
                            ),
                        )
                    )
                elif isinstance(file, str):
                    try:
                        if file.startswith("http"):
                            res = requests.get(file)
                            if res.status_code == 200:
                                content = res.content
                                parsed = urlparse(file)
                                filename = (
                                    os.path.basename(unquote(parsed.path))
                                    or f"audio_{idx}.mp3"
                                )
                            else:
                                print(f"Audio download failed: {res.status_code}")
                                continue
                        else:
                            with open(file, "rb") as f:
                                content = f.read()
                            filename = os.path.basename(file) or f"audio_{idx}.mp3"
                        data.append(
                            (
                                "file",
                                (filename, content, "application/octet-stream"),
                            )
                        )
                    except Exception as e:
                        print(f"Error while processing audio input: {e}")
                else:
                    print(f"Unsupported format: {type(file)}")
            except TypeError as e:
                print(f"Error while processing audio input: {e}")
                continue
        if len(data) > 0:
            payload_type = "audio" if len(data) == 1 else "audio_multiple"
            form_data = {"type": payload_type, "room": str(room_id)}
            if thread_id is not None:
                form_data["threadId"] = str(thread_id)
            res = requests.post(
                f"{self.iris_endpoint}/reply/multipart",
                data=form_data,
                files=data,
            )
            return self.__parse(res)
        else:
            print("No valid audio files to send.")

    def reply_video(
        self,
        room_id: int,
        files: t.List[BufferedIOBase | bytes | str],
        thread_id: int | None = None,
    ):
        if type(files) is not list:
            files = [files]
        data = []
        for idx, file in enumerate(files):
            try:
                if isinstance(file, BufferedIOBase):
                    name = getattr(file, "name", None)
                    filename = (
                        os.path.basename(str(name))
                        if name
                        else f"video_{idx}.mp4"
                    )
                    data.append(
                        ("file", (filename, file.read(), "application/octet-stream"))
                    )
                elif isinstance(file, bytes):
                    data.append(
                        (
                            "file",
                            (
                                f"video_{idx}.mp4",
                                file,
                                "application/octet-stream",
                            ),
                        )
                    )
                elif isinstance(file, str):
                    try:
                        if file.startswith("http"):
                            res = requests.get(file)
                            if res.status_code == 200:
                                content = res.content
                                parsed = urlparse(file)
                                filename = (
                                    os.path.basename(unquote(parsed.path))
                                    or f"video_{idx}.mp4"
                                )
                            else:
                                print(f"Video download failed: {res.status_code}")
                                continue
                        else:
                            with open(file, "rb") as f:
                                content = f.read()
                            filename = os.path.basename(file) or f"video_{idx}.mp4"
                        data.append(
                            (
                                "file",
                                (filename, content, "application/octet-stream"),
                            )
                        )
                    except Exception as e:
                        print(f"Error while processing video input: {e}")
                else:
                    print(f"Unsupported format: {type(file)}")
            except TypeError as e:
                print(f"Error while processing video input: {e}")
                continue
        if len(data) > 0:
            payload_type = "video" if len(data) == 1 else "video_multiple"
            form_data = {"type": payload_type, "room": str(room_id)}
            if thread_id is not None:
                form_data["threadId"] = str(thread_id)
            res = requests.post(
                f"{self.iris_endpoint}/reply/multipart",
                data=form_data,
                files=data,
            )
            return self.__parse(res)
        else:
            print("No valid video files to send.")

    def reply_file(
        self,
        room_id: int,
        files: t.List[BufferedIOBase | bytes | str],
        thread_id: int | None = None,
    ):
        if type(files) is not list:
            files = [files]
        data = []
        for idx, file in enumerate(files):
            try:
                if isinstance(file, BufferedIOBase):
                    name = getattr(file, "name", None)
                    filename = (
                        os.path.basename(str(name))
                        if name
                        else f"file_{idx}.bin"
                    )
                    data.append(
                        ("file", (filename, file.read(), "application/octet-stream"))
                    )
                elif isinstance(file, bytes):
                    data.append(
                        (
                            "file",
                            (
                                f"file_{idx}.bin",
                                file,
                                "application/octet-stream",
                            ),
                        )
                    )
                elif isinstance(file, str):
                    try:
                        if file.startswith("http"):
                            res = requests.get(file)
                            if res.status_code == 200:
                                content = res.content
                                parsed = urlparse(file)
                                filename = (
                                    os.path.basename(unquote(parsed.path))
                                    or f"file_{idx}.bin"
                                )
                            else:
                                print(f"File download failed: {res.status_code}")
                                continue
                        else:
                            with open(file, "rb") as f:
                                content = f.read()
                            filename = os.path.basename(file) or f"file_{idx}.bin"
                        data.append(
                            (
                                "file",
                                (filename, content, "application/octet-stream"),
                            )
                        )
                    except Exception as e:
                        print(f"Error while processing file input: {e}")
                else:
                    print(f"Unsupported format: {type(file)}")
            except TypeError as e:
                print(f"Error while processing file input: {e}")
                continue
        if len(data) > 0:
            payload_type = "file" if len(data) == 1 else "file_multiple"
            form_data = {"type": payload_type, "room": str(room_id)}
            if thread_id is not None:
                form_data["threadId"] = str(thread_id)
            res = requests.post(
                f"{self.iris_endpoint}/reply/multipart",
                data=form_data,
                files=data,
            )
            return self.__parse(res)
        else:
            print("No valid files to send.")
    # 추가끝