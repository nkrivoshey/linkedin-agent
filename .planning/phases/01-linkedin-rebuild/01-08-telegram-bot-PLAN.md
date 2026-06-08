---
phase: 01-linkedin-rebuild
plan: 8
type: execute
wave: 3
depends_on:
  - 01-04-context-store-questionnaire
files_modified:
  - modules/telegram_bot.py
autonomous: true
requirements:
  - REQ-03
  - REQ-04

must_haves:
  truths:
    - "Кнопка 🖼️ New Image добавлена в APPROVAL_KEYBOARD"
    - "Нажатие 🖼️ New Image регенерирует только изображение, текст поста не меняется"
    - "QuestionnaireState интегрирован в PostApprovalBot, не конфликтует с BotState"
    - "Ответы квестионнера сохраняются через on_context_entry callback"
    - "Существующие кнопки Publish/Regenerate/Skip работают без изменений"
  artifacts:
    - path: "modules/telegram_bot.py"
      provides: "PostApprovalBot с CALLBACK_NEW_IMAGE + QuestionnaireState интеграцией"
      contains: "CALLBACK_NEW_IMAGE"
  key_links:
    - from: "modules/telegram_bot.py CALLBACK_NEW_IMAGE"
      to: "on_new_image callback (main.py)"
      via: "Callable[[PostRecord], Coroutine] передан в конструктор"
      pattern: "on_new_image"
    - from: "modules/questionnaire.py QuestionnaireState"
      to: "modules/telegram_bot.py PostApprovalBot"
      via: "self._q_state = QuestionnaireState()"
      pattern: "_q_state|questionnaire"
---

<objective>
Обновить modules/telegram_bot.py: добавить кнопку "🖼️ New Image" в approval keyboard и интегрировать QuestionnaireState для обработки ответов квестионнера.

Purpose: REQ-03 (кнопка regenerate image), REQ-04 (квестионнер через тот же бот). Ключевое ограничение: существующий approval flow (Publish/Regenerate/Skip) не должен меняться.

Output: Обновлённый telegram_bot.py с двумя новыми возможностями.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/ROADMAP.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-CONTEXT.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/spikes/002-proactive-questionnaire/questionnaire_spike.py
</context>

<interfaces>
<!-- Существующий интерфейс из modules/telegram_bot.py -->
CALLBACK_PUBLISH = "publish"
CALLBACK_REGENERATE = "regenerate"
CALLBACK_SKIP = "skip"

APPROVAL_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Publish Now", callback_data=CALLBACK_PUBLISH),
    InlineKeyboardButton("✏️ Regenerate", callback_data=CALLBACK_REGENERATE),
    InlineKeyboardButton("❌ Skip", callback_data=CALLBACK_SKIP),
]])

class PostApprovalBot:
    def __init__(self, token, chat_id, on_publish, on_skip, on_regenerate,
                 on_custom_post=None, dry_run=False, manual_trigger=None)

Вызовы из main.py (сохранить сигнатуру):
    bot = PostApprovalBot(token=..., chat_id=..., on_publish=..., on_skip=...,
                          on_regenerate=..., on_custom_post=..., dry_run=..., manual_trigger=...)

<!-- Новые элементы -->

CALLBACK_NEW_IMAGE = "new_image"

Новый APPROVAL_KEYBOARD с 4 кнопками (2 ряда):
  Ряд 1: ✅ Publish Now | ✏️ Regenerate | ❌ Skip
  Ряд 2: 🖼️ New Image

Конструктор PostApprovalBot добавить параметры (с default=None):
  on_new_image: Callable[[PostRecord], Coroutine] | None = None
  on_context_entry: Callable[[str, str], Coroutine] | None = None  # (category, text) → None

В _handle_callback() добавить ветку elif action == CALLBACK_NEW_IMAGE:
  - Если self._state.current_record is None: игнорировать
  - await query.answer("🔄 Generating new image...")
  - if self.on_new_image: await self.on_new_image(self._state.current_record)

Интеграция QuestionnaireState:
  В __init__(): self._q_state = QuestionnaireState()
  В _handle_callback() добавить ветки для ctx_* callbacks из CATEGORIES (questionnaire_spike.py логика):
    if data in CALLBACK_TO_CATEGORY и self._q_state.active:
        category = CALLBACK_TO_CATEGORY[data]; self._q_state.category_selected(category)
        question = CATEGORIES[category]["question"]
        await query.edit_message_reply_markup(reply_markup=None)
        await ctx.bot.send_message(chat_id=self.chat_id, text=f"<b>{CATEGORIES[category]['label']}</b>\n\n{question}", parse_mode="HTML")
    elif data == CALLBACK_DONE и self._q_state.active:
        n = len(self._q_state.entries_this_session); self._q_state.finish()
        await query.edit_message_reply_markup(reply_markup=None)
        await ctx.bot.send_message(chat_id=self.chat_id, text=f"✅ Got {n} update{'s' if n != 1 else ''}! Next posts will feel alive 🔥")

  В _handle_text() добавить ПЕРЕД существующими проверками:
    if self._q_state.active and self._q_state.waiting_for_response:
        entry = self._q_state.response_received(update.message.text)
        if self.on_context_entry: await self.on_context_entry(entry["category"], entry["text"])
        await update.message.reply_text(f"📝 Saved! ({entry['category']})\n\nAdd another topic or tap Done:", parse_mode="HTML", reply_markup=category_keyboard())
        return  # НЕ передавать дальше в BotState handlers

Метод send_questionnaire(self) -> None (вызывается из планировщика main.py):
  - self._q_state.start()
  - Отправить сообщение "🧠 Weekly Context Update\n\nWhat do you want to share this week? Pick a category:"
  - С клавиатурой category_keyboard() из modules/questionnaire.py
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Добавить CALLBACK_NEW_IMAGE и QuestionnaireState в telegram_bot.py</name>
  <files>modules/telegram_bot.py</files>
  <read_first>
    - modules/telegram_bot.py — прочитать полностью перед изменением (критично: знать все существующие handlers)
    - modules/questionnaire.py — убедиться что QuestionnaireState, CATEGORIES, category_keyboard экспортируются (создан в плане 4)
    - .planning/spikes/002-proactive-questionnaire/questionnaire_spike.py — строки 263-302 (callback handler logic)
  </read_first>
  <action>
    Прочитать modules/telegram_bot.py полностью.

    Шаг 1 — Добавить CALLBACK_NEW_IMAGE в начало файла:
    После CALLBACK_SKIP = "skip" добавить:
    CALLBACK_NEW_IMAGE = "new_image"

    Шаг 2 — Обновить APPROVAL_KEYBOARD:
    Изменить на два ряда:
    InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publish Now", callback_data=CALLBACK_PUBLISH),
            InlineKeyboardButton("✏️ Regenerate", callback_data=CALLBACK_REGENERATE),
            InlineKeyboardButton("❌ Skip", callback_data=CALLBACK_SKIP),
        ],
        [
            InlineKeyboardButton("🖼️ New Image", callback_data=CALLBACK_NEW_IMAGE),
        ],
    ])

    Шаг 3 — Обновить __init__():
    Добавить параметры в конец (с default None):
    on_new_image: Callable[[PostRecord], Coroutine] | None = None
    on_context_entry: Callable[[str, str], Coroutine] | None = None
    Сохранить как self.on_new_image = on_new_image и self.on_context_entry = on_context_entry
    Добавить: from modules.questionnaire import QuestionnaireState, CATEGORIES, CALLBACK_TO_CATEGORY, CALLBACK_DONE, category_keyboard
    Добавить: self._q_state = QuestionnaireState()

    Шаг 4 — Обновить _handle_callback():
    Добавить в конец match-like цепочки elif:
    elif action == CALLBACK_NEW_IMAGE:
        if self._state.current_record is None: return
        await query.answer("🔄 Generating new image...")
        if self.on_new_image:
            await self.on_new_image(self._state.current_record)

    Добавить обработку questionnaire callbacks (ctx_work, ctx_life, ctx_learning, ctx_opinion, ctx_done):
    - Перед проверкой self._state.current_record is None добавить:
      if data in CALLBACK_TO_CATEGORY and self._q_state.active:
          [логика как в интерфейсе выше]
          return
      if data == CALLBACK_DONE and self._q_state.active:
          [логика завершения]
          return

    Шаг 5 — Обновить _handle_text():
    В начале метода (ПЕРЕД existing checks) добавить:
    if self._q_state.active and self._q_state.waiting_for_response:
        entry = self._q_state.response_received(update.message.text)
        if self.on_context_entry:
            await self.on_context_entry(entry["category"], entry["text"])
        await update.message.reply_text(...)
        return

    Шаг 6 — Добавить метод send_questionnaire():
    async def send_questionnaire(self) -> None:
        self._q_state.start()
        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text="🧠 <b>Weekly Context Update</b>\n\nWhat do you want to share this week?\nPick a category:",
            parse_mode="HTML",
            reply_markup=category_keyboard(),
        )
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import inspect
from modules.telegram_bot import PostApprovalBot, CALLBACK_NEW_IMAGE, APPROVAL_KEYBOARD

assert CALLBACK_NEW_IMAGE == 'new_image'
# APPROVAL_KEYBOARD должен иметь 2 ряда кнопок
kb = APPROVAL_KEYBOARD.inline_keyboard
assert len(kb) == 2, f'Expected 2 rows, got {len(kb)}'
assert len(kb[0]) == 3, f'Expected 3 buttons in row 1, got {len(kb[0])}'
assert len(kb[1]) == 1, f'Expected 1 button in row 2, got {len(kb[1])}'
assert kb[1][0].callback_data == 'new_image'

sig = inspect.signature(PostApprovalBot.__init__)
assert 'on_new_image' in sig.parameters
assert 'on_context_entry' in sig.parameters

assert hasattr(PostApprovalBot, 'send_questionnaire')
print('PostApprovalBot interface OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - APPROVAL_KEYBOARD имеет 2 ряда: [Publish, Regenerate, Skip] и [New Image]
    - CALLBACK_NEW_IMAGE == "new_image"
    - PostApprovalBot.__init__() принимает on_new_image и on_context_entry (оба с default=None)
    - send_questionnaire() метод существует
    - Существующий код в main.py создающий PostApprovalBot без новых параметров работает (обратная совместимость)
    - _handle_text() обрабатывает questionnaire ПЕРЕД BotState handlers — проверить порядок if-ов в исходнике
    - python -c "from modules.telegram_bot import PostApprovalBot, CALLBACK_NEW_IMAGE" без ошибок
  </acceptance_criteria>
  <done>telegram_bot.py обновлён: кнопка New Image добавлена, QuestionnaireState интегрирован, on_new_image/on_context_entry callbacks добавлены, существующий flow сохранён</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Telegram callback_data → handler | callback_data строки; проверяются через if/elif |
| Telegram free text → context_entry | текст пользователя передаётся в on_context_entry callback |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-01 | Spoofing | Telegram chat_id | accept | бот отвечает только на сообщения из chat_id из env |
| T-08-02 | Tampering | callback_data манипуляция | mitigate | проверка через if data in CALLBACK_TO_CATEGORY (whitelist) |
| T-08-03 | DoS | on_new_image медленная (~25s gpt-image-1) | mitigate | query.answer() вызвать немедленно чтобы снять pending state у Telegram |
| T-08-SC | Tampering | pip installs | accept | python-telegram-bot уже в requirements.txt |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.telegram_bot import (
    PostApprovalBot, CALLBACK_NEW_IMAGE, CALLBACK_PUBLISH, CALLBACK_SKIP,
    CALLBACK_REGENERATE, APPROVAL_KEYBOARD
)
import inspect

# Keyboard structure
kb = APPROVAL_KEYBOARD.inline_keyboard
assert len(kb) == 2
row1_data = [b.callback_data for b in kb[0]]
assert row1_data == ['publish', 'regenerate', 'skip']
row2_data = [b.callback_data for b in kb[1]]
assert row2_data == ['new_image']

# Bot constructor accepts new params
sig = inspect.signature(PostApprovalBot.__init__)
assert sig.parameters['on_new_image'].default is None
assert sig.parameters['on_context_entry'].default is None

# send_questionnaire exists
assert hasattr(PostApprovalBot, 'send_questionnaire')

# _handle_text checks questionnaire first
src = inspect.getsource(PostApprovalBot._handle_text)
q_pos = src.find('_q_state')
custom_pos = src.find('waiting_for_custom_text')
assert q_pos < custom_pos, 'Questionnaire check must come before BotState check'

print('PASS: telegram_bot OK')
"
</verification>

<success_criteria>
- 🖼️ New Image кнопка видна в preview сообщении (второй ряд)
- Нажатие New Image вызывает on_new_image callback
- Questionnaire flow не мешает Publish/Regenerate/Skip
- Существующие tests в main.py на build_pipeline не сломаны
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-08-SUMMARY.md` when done
</output>
