# schemas/user/__init__.py
"""用户功能相关 schemas"""

from .submissions import *
from .suggestions import *
from .custom_mutations import (
    BatchUpdateRequest,
    BatchDeleteByIdRequest,
    SaveCustomDataRequest,
)
