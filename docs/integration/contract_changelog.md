# Contract changelog

## 2.1.0-a02

CR-B01 is accepted with a backward-compatible public representation for structured answers.

- `Message.structured_content` and `ExportMessage.structured_content` are optional and contain
  `summary`, `conditions`, and `steps`. The existing required plain-text `content`/`text` remains
  canonical for clients that do not consume structured sections.
- Frozen `RequestView` fixtures now cover `queued`, `retrieving`, and `sources_found` progress.
- A frozen `SourceRecord` fixture for `source-demo` supplies only explicitly mock, nullable metadata.
- No endpoint or existing required request/response field was removed or renamed.

B02 should render `structured_content` when present and fall back to the plain string when absent.
