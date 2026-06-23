from dataclasses import dataclass, field


@dataclass
class ParsedSlide:
    slide_no: int
    title: str
    body: str
    notes: str

    @property
    def text(self) -> str:
        parts = []
        if self.title:
            parts.append(self.title)
        if self.body:
            parts.append(self.body)
        if self.notes:
            parts.append(self.notes)
        return "\n".join(parts)

    def __len__(self) -> int:
        return len(self.text)


@dataclass
class ParsedDocument:
    doc_id: str
    source_path: str
    file_type: str          # "pptx" | "pdf"
    slides: list[ParsedSlide] = field(default_factory=list)

    @property
    def total_slides(self) -> int:
        return len(self.slides)
