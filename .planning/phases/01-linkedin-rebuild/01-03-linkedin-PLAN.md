---
phase: 01-linkedin-rebuild
plan: 3
type: execute
wave: 1
depends_on: []
files_modified:
  - modules/linkedin.py
autonomous: true
requirements:
  - REQ-11

must_haves:
  truths:
    - "LinkedInPublisher.publish() принимает image_bytes: bytes | None"
    - "_upload_image_bytes(bytes) загружает изображение без скачивания по URL"
    - "Существующий путь через image_url сохранён без изменений"
  artifacts:
    - path: "modules/linkedin.py"
      provides: "LinkedInPublisher с _upload_image_bytes() и обновлённым publish()"
      contains: "_upload_image_bytes"
  key_links:
    - from: "modules/images.py fetch_gpt_image()"
      to: "modules/linkedin.py _upload_image_bytes()"
      via: "bytes переданы через publish(image_bytes=...)"
      pattern: "image_bytes"
---

<objective>
Добавить метод _upload_image_bytes() в LinkedInPublisher и обновить сигнатуру publish() для поддержки прямой передачи bytes из gpt-image-1.

Purpose: gpt-image-1 возвращает base64 PNG (~2MB) — не URL. Текущий _upload_image() делает GET-запрос по URL. Новый метод принимает bytes напрямую и пропускает шаг скачивания (REQ-11).

Output: Обновлённый modules/linkedin.py; publish() поддерживает оба пути: image_url (старый) и image_bytes (новый).
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/ROADMAP.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-CONTEXT.md
</context>

<interfaces>
<!-- Текущий интерфейс из modules/linkedin.py -->

class LinkedInPublisher:
    def publish(self, text: str, image_url: str) -> str
    def _upload_image(self, image_url: str) -> str | None   # GET image_url → PUT bytes
    def is_token_expiring_soon(self, warn_at_day: int = 55) -> bool

Вызов publish() в main.py (on_publish):
    url = linkedin.publish(text=record.post_text, image_url=record.image_url)
    → Этот вызов должен продолжить работать без изменений.

Новая сигнатура publish() (D-08 из CONTEXT.md):
    def publish(self, text: str, image_url: str = "", image_bytes: bytes | None = None) -> str
    Приоритет: если image_bytes задан → _upload_image_bytes(image_bytes)
              иначе если image_url задан → _upload_image(image_url) (существующий путь)
              иначе → image_urn = None (пост без изображения)

Новый метод _upload_image_bytes(image_bytes: bytes) -> str | None:
    - Шаг 1: POST /assets?action=registerUpload (то же тело что в _upload_image)
    - Шаг 2: PUT upload_url с data=image_bytes (пропустить requests.get шаг)
    - Вернуть asset_urn или None при ошибке
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Добавить _upload_image_bytes() и обновить publish()</name>
  <files>modules/linkedin.py</files>
  <read_first>
    - modules/linkedin.py — прочитать полностью перед изменением
  </read_first>
  <action>
    Прочитать modules/linkedin.py.

    Изменить сигнатуру publish():
    - Было: publish(self, text: str, image_url: str) -> str
    - Стало: publish(self, text: str, image_url: str = "", image_bytes: bytes | None = None) -> str

    В теле publish() заменить первую строку:
    - Было: image_urn = self._upload_image(image_url) if image_url else None
    - Стало:
      if image_bytes is not None:
          image_urn = self._upload_image_bytes(image_bytes)
      elif image_url:
          image_urn = self._upload_image(image_url)
      else:
          image_urn = None

    Добавить новый метод _upload_image_bytes(self, image_bytes: bytes) -> str | None сразу после _upload_image():
    - Шаг 1 (register): отправить POST /assets?action=registerUpload с тем же register_payload что в _upload_image; если статус != 200 вернуть None
    - Извлечь upload_url и asset_urn из resp.json() идентично _upload_image()
    - Шаг 2 (upload): PUT upload_url с data=image_bytes и headers={"Authorization": f"Bearer {self.access_token}"}; timeout=60
    - Вернуть asset_urn
    - Обернуть в try/except Exception: logger.exception("LinkedIn image bytes upload failed"), return None

    Добавить import logging и logger = logging.getLogger(__name__) если их нет.

    Существующий метод _upload_image() не менять.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import inspect
from modules.linkedin import LinkedInPublisher
sig = inspect.signature(LinkedInPublisher.publish)
params = sig.parameters
assert 'image_bytes' in params, 'image_bytes param missing'
assert 'image_url' in params
assert params['image_url'].default == '', 'image_url should have default empty string'
assert hasattr(LinkedInPublisher, '_upload_image_bytes'), '_upload_image_bytes missing'
print('LinkedInPublisher interface OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - publish(text="t", image_url="http://x.com/img.jpg") работает (обратная совместимость)
    - publish(text="t", image_bytes=b"fake_png_bytes") не вызывает AttributeError
    - publish(text="t") работает без image (image_urn=None)
    - _upload_image_bytes существует и принимает bytes
    - _upload_image() не изменён
    - python -c "from modules.linkedin import LinkedInPublisher" работает без ошибок
  </acceptance_criteria>
  <done>LinkedInPublisher.publish() поддерживает image_bytes: bytes | None; _upload_image_bytes() реализован; обратная совместимость сохранена</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| image_bytes → LinkedIn API | bytes передаются напрямую без дополнительной валидации |
| LinkedIn Bearer token → API | токен из env, не логируется |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01 | Tampering | image_bytes содержимое | accept | bytes от OpenAI gpt-image-1; не исполняются, только загружаются в LinkedIn |
| T-03-02 | Denial of Service | PUT upload timeout | mitigate | timeout=60 задан явно; исключение перехватывается, возвращает None |
| T-03-SC | Tampering | pip installs | accept | план не устанавливает новых зависимостей |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.linkedin import LinkedInPublisher
import inspect
sig = inspect.signature(LinkedInPublisher.publish)
p = sig.parameters
assert 'image_bytes' in p
assert p['image_bytes'].default is None
assert p['image_url'].default == ''
assert hasattr(LinkedInPublisher, '_upload_image_bytes')
src = inspect.getsource(LinkedInPublisher._upload_image_bytes)
assert 'registerUpload' in src
assert 'image_bytes' in src
print('PASS: linkedin module OK')
"
</verification>

<success_criteria>
- publish() принимает image_bytes=bytes и делегирует в _upload_image_bytes()
- _upload_image_bytes() пропускает GET-запрос, отправляет bytes напрямую
- on_publish в main.py (вызывает publish(text=..., image_url=...)) продолжает работать
- Импорт без ошибок
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-03-SUMMARY.md` when done
</output>
