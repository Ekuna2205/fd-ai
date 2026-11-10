import enum


class RoleName(str, enum.Enum):
    ADMINISTRATOR = "administrator"
    RESEARCHER = "researcher"
    OPERATOR = "operator"
    VIEWER = "viewer"


class VerificationStatus(str, enum.Enum):
    REAL = "REAL"
    FAKE = "FAKE"
    UNCERTAIN = "UNCERTAIN"
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    PROCESSING = "PROCESSING"
    ERROR = "ERROR"


class SpoofType(str, enum.Enum):
    PRINTED_PHOTO = "PRINTED_PHOTO"
    PHONE_SCREEN = "PHONE_SCREEN"
    COMPUTER_SCREEN = "COMPUTER_SCREEN"
    REPLAY_VIDEO = "REPLAY_VIDEO"
    OTHER = "OTHER"


class SessionMode(str, enum.Enum):
    LIVE = "LIVE"
    UPLOAD_IMAGE = "UPLOAD_IMAGE"
    UPLOAD_VIDEO = "UPLOAD_VIDEO"


class ChallengeType(str, enum.Enum):
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    LOOK_UP = "LOOK_UP"
    BLINK = "BLINK"


class FileStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    REJECTED = "REJECTED"
    DELETED = "DELETED"


class DatasetSource(str, enum.Enum):
    LABEL_STUDIO = "LABEL_STUDIO"
    CSV = "CSV"
    JSON = "JSON"
    MEDIA = "MEDIA"


class SampleLabel(str, enum.Enum):
    REAL = "REAL"
    PRINTED_PHOTO = "PRINTED_PHOTO"
    PHONE_SCREEN = "PHONE_SCREEN"
    COMPUTER_SCREEN = "COMPUTER_SCREEN"
    REPLAY_VIDEO = "REPLAY_VIDEO"
    UNKNOWN = "UNKNOWN"


class DataSplit(str, enum.Enum):
    TRAIN = "TRAIN"
    VAL = "VAL"
    TEST = "TEST"
