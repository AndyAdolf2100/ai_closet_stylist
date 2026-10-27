class StylistError(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        self.code, self.message, self.status = code, message, status
        super().__init__(code)


class AuthenticationExpired(StylistError):
    def __init__(self):
        super().__init__("authentication_expired", "登录状态已失效，请重新登录。你的原需求会保留。", 401)
