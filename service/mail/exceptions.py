"""우편 시스템 예외"""

from exceptions import CUHABotError


class MailError(CUHABotError):
    """우편 시스템 기본 예외"""
    pass


class MailNotFoundError(MailError):
    """우편을 찾을 수 없음"""

    def __init__(self, mail_id: int):
        self.mail_id = mail_id
        super().__init__(f"우편을 찾을 수 없습니다 (ID: {mail_id})")


class AlreadyClaimedError(MailError):
    """이미 수령한 보상"""

    def __init__(self, message: str = "이미 수령한 보상입니다"):
        super().__init__(message)


class NoRewardError(MailError):
    """첨부된 보상이 없음"""

    def __init__(self, message: str = "첨부된 보상이 없습니다"):
        super().__init__(message)


class ExpiredMailError(MailError):
    """만료된 우편"""

    def __init__(self, message: str = "만료된 우편입니다"):
        super().__init__(message)


class CannotDeleteError(MailError):
    """삭제할 수 없음"""

    def __init__(self, message: str = "보상을 먼저 수령해주세요"):
        super().__init__(message)
