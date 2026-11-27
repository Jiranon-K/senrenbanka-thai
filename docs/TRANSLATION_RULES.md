# Translation rules

Rules for every Thai line in this patch. Each rule has an ID and a named
enforcer. A reviewer flag cites a rule ID. A rule with no enforcer is a wish:
add the check before relying on it.

Enforcers: `lint` is `python -m tools.review lint`. `reviewer` is the LLM
Reviewer stage (`python -m tools.review review`). `owner` is a human decision
recorded in `thai_work/glossary.csv` or `thai_work/characters.csv`.

This file is also the first part of the Reviewer and Reviser system prompt, so
it is written for a model to apply line by line. The invariants of the build
pipeline live in [RULES.md](RULES.md) and are a different list.

## Source authority

| ID | Rule | Enforcer |
|---|---|---|
| S1 | Japanese is the only source of meaning. English is a reference that localizes freely. Chinese is the tiebreaker. A Thai line that follows the English where the English departs from the Japanese is wrong. | reviewer |
| S2 | Nothing is dropped or summarized. Every clause, hedge, repetition and broken-off sentence in the Japanese has a counterpart in the Thai line with the same idx. Content never moves to a neighbouring line. | lint (length ratio), reviewer |
| S3 | Nothing is added. No extra adjectives, intensifiers, explanations, or details that only the English has. Thai may add a subject pronoun the Japanese omitted, and nothing else. | reviewer |
| S4 | Degree and certainty are kept: a little stays a little, a guess stays a guess, a question stays a question. | reviewer |

## Characters

| ID | Rule | Enforcer |
|---|---|---|
| C1 | Speaker gender comes from `thai_work/characters.csv`, never from a romanised name. ครับ and ผม belong to male speakers. ค่ะ, คะ and ดิฉัน belong to female speakers. Text inside inner quotes is quoted speech and follows the quoted person. A speaker with no recorded sex gets no gendered particle and no gendered self-pronoun. | lint, reviewer |
| C2 | Each speaker keeps the self-pronoun, particle and voice in the character table. Murasame speaks archaic but cute Thai (ข้า, เจ้า, นายท่าน) with no modern polite particle and no loanwords. Mako and Yoshino speak modern polite Thai with no archaic particles. Lena's odd Japanese becomes consistent, slightly stiff and over-formal Thai, never male particles and never random misspelling. Register is never coarser than the Japanese: no กู, มึง or vulgar words unless the Japanese is itself vulgar. | reviewer |
| C3 | Kinship follows the side of the family, taken from evidence only. Genjuurou is the maternal grandfather of Masaomi (ตา, คุณตา) and the paternal grandfather of Rentarou and Koharu (ปู่, คุณปู่). Their father is the elder brother of Masaomi's mother (ลุง to Masaomi). A third party speaking to one of them uses that person's term. A relative whose side is not evidenced is queued for the owner and never guessed. An unrelated elderly person is คุณตา or คุณยาย. | lint, reviewer |
| C4 | Address terms follow the Japanese of that exact line: surname or given name, with or without a title. さん is คุณ in front of the name, 様 is ท่าน (お嬢様 is คุณหนู), ちゃん stays จัง after the name, a bare name stays bare. Never stack คุณ on a kept suffix. When a line is about the form of address itself (dropping さん, asking for a nickname), the change must be visible in Thai, and narration must not make the switch earlier than the Japanese does. | reviewer |
| C5 | Royal vocabulary belongs to deities and royalty only. The verb prefix ทรง is never used for a teacher, an elder or any other ordinary person, however polite the Japanese is; politeness is carried by ท่าน, คุณ and the polite particle. | lint |

## Jokes and wordplay

| ID | Rule | Enforcer |
|---|---|---|
| J1 | A joke keeps what it is about, who it is aimed at, and where the punchline lands. A line that only explains the joke fails. | reviewer |
| J2 | A pun on Japanese sound or kanji is carried, in order of preference: a Thai pun on the same meaning pair; a Thai pun on another word pair with the same target and punchline position; the Japanese word kept with a gloss of a few words spoken naturally inside the line. The line after a pun must still make sense as a reaction to it, so review the pair together. | reviewer, owner |
| J3 | No joke is added where the Japanese has none. No Thai celebrity, brand, television or place reference replaces a Japanese one. No translator notes, asterisks or bracketed explanations aimed at the reader inside a text field. | reviewer |
| J4 | A reference to another work is translated as the reference it is. The Thai does not name a work that the Japanese only alludes to. | reviewer |

## Wording

| ID | Rule | Enforcer |
|---|---|---|
| L1 | Use natural, contemporary Thai that people say today. Casual lines may use current colloquial words that have stayed in use for years (โคตร, ชิล, เนียน, มโน, ฟิน, เว่อร์). Stiff literal phrasing is a fault where the Japanese is casual. | reviewer |
| L2 | Slang level matches the Japanese line. Plain Japanese stays plain Thai. Narration and Murasame never use slang. Chat spellings and 555 never appear. Dated forms are not used: ตู, เอ็ง, ยัยบ๊อง, ตาบ้า, อะจ๊าก, ไอ้หยา. Thai-Chinese family words (อาตี๋, อาหมวย, อาเฮีย, อาเจ๊, อาม่า, อากง) never stand in for a Japanese pronoun or name. | lint (the Thai-Chinese family words, ยัยบ๊อง, อะจ๊าก, ไอ้หยา), reviewer |
| L3 | Ritual set phrases are translated by function (いただきます, ただいま, お疲れ様), unless a joke depends on the Japanese form. | reviewer |
| L4 | Screams, gasps and sound effects become Thai sound words that fit the emotion, not a syllable copy of the kana. Lengthening repeats a final letter a few times and matches the length of the voiced line. | reviewer |

## Terms and names

| ID | Rule | Enforcer |
|---|---|---|
| N1 | A term in `thai_work/glossary.csv` is written exactly as the glossary has it. | lint |
| N2 | A rendering in the glossary's `forbidden` column never appears for that term. | lint |
| N3 | One Thai spelling per name. Readings come from the game's furigana, its voice, or an outside source, never from guessing kanji. Words already established in Thai keep their established spelling. | lint, owner |
| N4 | Culture-specific items keep their Japanese name when Thai readers know them or when the item is the topic of the line. Shrine vocabulary never uses Buddhist temple words (วัด, พระ). Money, measures and school years stay Japanese. | reviewer |

## Form

| ID | Rule | Enforcer |
|---|---|---|
| F1 | A Thai line opens and closes with the same quote bracket as its Japanese line, and has none when the Japanese has none. | lint |
| F2 | No kana or kanji remains in a Thai line. | lint |
| F3 | A Thai line is not empty when its Japanese line has words. | lint |
| F4 | Size tags keep their count. Ruby readings are dropped. A literal `\n` between two quoted utterances is kept. Any other `\n` in the Japanese is Japanese line wrapping: the Thai line may drop it, and never has more than the Japanese. | lint |
| F5 | A Thai line uses only characters the game font draws: Thai, ASCII, and the punctuation `「」『』【】（）、。・〜～…―—！？♪“”‘’`. A Japanese censor mark such as ○ becomes `*`, and ☆ becomes ♪. | lint |
| F6 | A literal `\n` never strands a fragment. No line is left empty, and a piece shorter than six letters stands alone only after a finished sentence or as its own quoted utterance. A line that fits the text box without the break has none. | lint (fragments); the fit is measured by hand against the 1154 px text box |

## Project conventions that are never a defect

A reviewer flag against any of these is itself wrong.

- さん written as คุณ in front of the name, ちゃん kept as จัง, 様 as ท่าน.
- Japanese quote brackets `「」 『』` kept in the Thai line.
- Masaomi's ผม in narration and speech, and a subject pronoun added where Thai needs one.
- A natural Thai sentence particle or idiom that carries no meaning the Japanese lacks.
- Contemporary colloquial Thai on a casual Japanese line.
- Name spellings and terms exactly as the glossary has them.

## Process

| ID | Rule | Enforcer |
|---|---|---|
| P1 | The Reviewer runs in a fresh context and judges only the Japanese against the Thai. It never sees translator reasoning and never flags a style preference. | reviewer prompt |
| P2 | Outside sources (VNDB, other translations) settle facts only. They never supply wording. | owner |
| P3 | A correction that recurs becomes a lint rule or a glossary row, not more prompt text. | owner |
| P4 | Every API call is written to the spend ledger, and a submit that would pass the cap is refused. | `tools.review` |
