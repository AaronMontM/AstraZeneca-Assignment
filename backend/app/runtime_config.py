from dataclasses import asdict, dataclass

from app.config import settings


@dataclass
class RuntimeConfig:
    model: str
    temperature: float
    max_history_messages: int

    @classmethod
    def from_settings(cls):
        return cls(
            model=settings.OLLAMA_MODEL,
            temperature=settings.TEMPERATURE,
            max_history_messages=settings.MAX_HISTORY_MESSAGES,
        )

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self):
        return asdict(self)