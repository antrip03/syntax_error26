"""One-shot, idempotent-by-assertion reskin of the detective game into the finance audit game (branch finance-ui).
Every replacement must match exactly once (or the listed count); a mismatch aborts so nothing is silently skipped."""
import re
import sys

ROOT = "game/"
R = []  # (file, old, new, expected_count)


def rep(f, old, new, n=1):
    R.append((f, old, new, n))


# ---------- index.html ----------
rep("index.html", "<title>The Killing at Vaudville</title>", "<title>The Audit at Tickerville</title>")
rep("index.html", "Lighting the lanterns of Vaudville…", "Opening the markets of Tickerville…")

# ---------- title screen / menus ----------
m = "js/ui/menus.js"
rep(m, 'import { CASE } from "../data/elsie.js";', 'import { CASE } from "../data/market.js";')
rep(m, '"A murder mystery"', '"A financial-audit mystery"')
rep(m, 'h("h1", {}, "The Killing at ", h("span", {}, "Vaudville"))', 'h("h1", {}, "The Audit at ", h("span", {}, "Tickerville"))')
rep(m, "Every villager is the same small language model, reading different private documents. The trained ones only say what they can cite. Find the one whose records don't add up.",
    "Every desk in Tickerville is a small language model showing its work on the same return series. A deterministic verifier recomputes every line it writes. Find the desk whose numbers don't add up. The models analyse the series they are given; nobody here predicts the market.")
rep(m, "6 villagers, 3 days, 15 questions a day. Witnesses name the killer; clash hints", "5 desks, 3 days, 15 questions a day. Green/red badges from the verifier; clash hints")
R.append((m, r'RE:8 villagers, 2 days, 7 questions a day\.[^"]*', "6 desks, 2 days, 7 questions a day. Badges hidden: spend verify checks. One wrong flag ends the audit.", 1))
rep(m, 'h("label", {}, "Villagers")', 'h("label", {}, "Floor")')
rep(m, '[["grounded", "Grounded", "Trained adapter: cites sources, abstains when unsure"], ["base", "Base", "Untrained base model: guesses freely"]]',
    '[["grounded", "Trained desks", "Only the trained models are on the floor"], ["base", "With the baseline", "Adds the untrained base model (it never shows checkable work)"]]')
rep(m, '"Planted rumour"', '"Planted bad figure"', 2)
rep(m, "Whisper a false rumour to one villager as if a traveller said it, then let the village gossip for 5 rounds. Untrained villagers repeat it as fact. Grounded ones pass it on, if at all, as hearsay with “no record”.",
    "Whisper a false figure to one desk as if a trader said it, then let the desks compare notes for 5 rounds. Untrained desks repeat it as fact. Trained ones pass it on, if at all, as hearsay with “no record”.")
rep(m, '"Whisper it to"', '"Whisper it to desk"')
rep(m, '"The rumour"', '"The figure"')
rep(m, "Walk up to a villager and press ", "Walk up to a desk and press ")
rep(m, "green = backed by the villager's own document (the quote is shown), red = not backed, grey = the villager said it's not in their records.",
    "green = the verifier recomputed the same value from the tape (the recompute is shown), red = the value doesn't match, grey = the desk said it has no working for that.")
rep(m, 'h("li", {}, h("b", {}, "Pin "), "green claims. Open the ", h("b", {}, "Board"), " (", h("kbd", {}, "B"), ") and link two claims that can\'t both be true."),',
    'h("li", {}, h("b", {}, "Pin "), "green lines. Open the ", h("b", {}, "Board"), " (", h("kbd", {}, "B"), ") and link two lines from different desks that disagree on the same step."),')
rep(m, "ending the day lets villagers gossip. They may repeat what they heard, but must say who told them.",
    "ending the day starts peer review: desks compare notes. They may repeat what they heard, but must say who told them.")
rep(m, '"with 2 confirmed contradictions plus a pinned motive. Wrong accusations cost strikes."', '"a desk with 2 confirmed contradictions plus a pinned line showing the true final figure. Wrong flags cost strikes."')
rep(m, '"Accuse "', '"Flag "')
rep(m, '"Grounded vs Base: "', '"Trained vs baseline: "')
rep(m, "the same seed with the trained adapter on or off. Compare how often each village makes things up.", "the same audit with the untrained baseline on the floor or not. Compare how often each floor writes steps that fail the recompute.")
rep(m, '"Detective → "', '"Auditor → "')
rep(m, "start the FastAPI server and reload to use the real villagers", "start the FastAPI server and reload to use live models")

# ---------- play.js ----------
p = "js/ui/play.js"
rep(p, "Writing a new mystery for Vaudville…", "Pulling a new audit file for Tickerville…")
rep(p, "The sun is setting over Vaudville. End the day when you're ready.", "The market is closing over Tickerville. End the day when you're ready.")
rep(p, "Townsfolk chat is just local colour. Only the case villagers keep records you can check.", "Townsfolk chat is just local colour. Only the model desks show workings you can check.")
rep(p, '"A death in Vaudville"', '"A bad number in Tickerville"')
rep(p, '"The village wakes"', '"The market opens"')
rep(p, "Walk up to villagers (WASD / arrows, or click the ground) and press ", "Walk up to desks (WASD / arrows, or click the ground) and press ")
rep(p, "Every claim is checked against the villager's own documents: ", "Every line a desk writes is recomputed from the tape by the verifier: ")
rep(p, "Pin green claims. On the board, link two pinned claims that can't both be true.", "Pin green lines. On the board, link two lines from different desks that disagree on the same step.")
rep(p, "Accuse with at least 2 confirmed contradictions involving the killer, plus a pinned motive.", "Flag the faulty desk with at least 2 confirmed contradictions involving it, plus a pinned line showing the true final figure.")
rep(p, '"The chalk outline"', '"The audit file"')
rep(p, '"The guildhall side door"', '"Compliance Hall"')
rep(p, "Chalk marks the floor where ${game.victim.name} was found. A few dark stains, the side door still ajar. ${game.briefing}", "Chalk marks on the compliance floor circle ${game.victim.name}. ${game.briefing}")
rep(p, "${game.briefing} The side door hangs open on its latch.", "${game.briefing} The tape is pinned to the wall for everyone to read.")
rep(p, '"Where were you on the night of the murder?"', '"Show me your work, step by step."')
rep(p, "`What do you know about ${game.victim.name}?`", '"What is your final figure?"')
rep(p, "`Who did you see near the ${game.scene} on day 2?`", '"Walk me through the return figures."')
rep(p, "`When did you last see ${other.name}?`", "`Do you trust ${other.name}'s numbers?`")
rep(p, "`Did anyone quarrel with ${game.victim.name}?`", '"What did you get for the drawdown or volatility steps?"')
rep(p, '"Tell me about your records."', '"How do you combine the pieces?"')
rep(p, '"What did anyone tell you last night?"', '"What did the other desks tell you last night?"')
rep(p, 'hudBtn("accuse", "Accuse", openAccuse, "warn")', 'hudBtn("accuse", "Flag a desk", openAccuse, "warn")')
rep(p, '"Strikes left (wrong accusations)"', '"Strikes left (wrong flags)"')
rep(p, '"Make an accusation"', '"Flag a desk"')
rep(p, "A wrong accusation costs a strike", "A wrong flag costs a strike")
rep(p, '"1 · Who did it?"', '"1 · Which desk\'s figure is wrong?"')
rep(p, '"3 · Motive"', '"3 · The true figure"')
rep(p, '"Pin the claim that shows the motive."', '"Pin the line that shows the correct final figure (ask a desk for its final figure)."')
rep(p, "`Accuse ${nameOf(suspect)}` : \"Accuse\"", "`Flag ${nameOf(suspect)}` : \"Flag\"")
rep(p, "is not charged.", "is not flagged.")
rep(p, "The motive doesn't hold.", "That line doesn't show the true figure.")
rep(p, '"Case closed"', '"Audit closed"')
rep(p, '"Case unsolved"', '"Audit unresolved"')
rep(p, "`You caught ${nameOf(suspect)}!`", "`You flagged ${nameOf(suspect)}!`")
rep(p, '"The village has lost faith in you"', '"The firm has lost faith in you"')
rep(p, "`The killer: ${nameOf(reveal.killer)}`", "`The faulty desk: ${nameOf(reveal.killer)}`")
rep(p, "The truth stays buried. (The backend reveals the killer once the game is over.)", "The answer stays sealed. (The verifier reveals it once the game is over.)")
rep(p, '`Grounding report · ${game.settings.mode === "grounded" ? "Grounded" : "Base"} village`', '`Verifier report · ${game.settings.mode === "grounded" ? "Trained floor" : "Floor with the baseline"}`')
rep(p, '"supported claims"', '"verified lines"')
rep(p, '"unsupported claims"', '"failed lines"')
rep(p, '"honest abstains"', '"honest “no working”"')
rep(p, '"unsupported-claim rate"', '"failed-line rate"')
rep(p, 'h("th", {}, "Base"), h("th", {}, "Grounded")', 'h("th", {}, "With baseline"), h("th", {}, "Trained only")')
rep(p, '["Unsupported-claim rate"', '["Failed-line rate"')
rep(p, '["Supported claims"', '["Verified lines"')
rep(p, '["Unsupported claims"', '["Failed lines"')
rep(p, "`Play the same seed with the ${other} village to compare them side by side.`", "`Play the same audit with the ${other === \"base\" ? \"baseline included\" : \"trained desks only\"} to compare.`")
rep(p, '`Replay this case · ${other === "base" ? "Base" : "Grounded"} village`', '`Replay this audit · ${other === "base" ? "with baseline" : "trained only"}`')

# ---------- encounter ----------
rep("js/ui/encounter.js", 'h("b", {}, "Detective")', 'h("b", {}, "Auditor")')

# ---------- map labels / chatter ----------
mp = "js/map.js"
rep(mp, "// Vaudville layout", "// Tickerville layout")
rep(mp, 'title: "Bakery"', 'title: "Quant Bakery"')
rep(mp, 'title: "The Drowsy Goose Inn"', 'title: "The Exchange Inn"')
rep(mp, 'title: "Guildhall"', 'title: "Compliance Hall"')
rep(mp, 'title: "Chapel"', 'title: "Risk Chapel"')
rep(mp, 'title: "Smithy"', 'title: "The Pricing Forge"')
rep(mp, 'title: "Mill"', 'title: "The Data Mill"')
rep(mp, 'title: "Herb cottage"', 'title: "Cash-Flow Cottage"')
rep(mp, "Fresh apples! Two for a copper!", "Fresh apples! Two for a basis point!")
rep(mp, "Turnips fat as your fist, detective.", "Turnips fat as your fist, auditor.")
rep(mp, "Business is slow since the guildhall business.", "Volumes are thin since the audit began.")
rep(mp, "Vaudville's seen hard winters, but nothing like this.", "Tickerville's seen bear markets, but nothing like this.")
rep(mp, "Speak to folk who wrote it down, dear. Memory is a liar.", "Trust the ones who show their arithmetic, dear. Memory is a liar.")
rep(mp, "Are you a real detective?!", "Are you a real auditor?!")
rep(mp, "Nobody touches the guildhall floor. Orders.", "Nobody touches the audit file. Orders.")
rep(mp, "Place feels empty without {victim}.", "Trading feels odd while {victim} is open.")
rep(mp, "To {victim}.", "To a clean {victim}.")
rep(mp, "Don't step on the chalk, please.", "Don't smudge the tape, please.")
rep(mp, "The records office is closed until further notice.", "The ledger room is closed until further notice.")
rep(mp, "Ink, paper, seals. That's the guild.", "Ink, paper, seals. That's compliance.")
rep(mp, "Shh. I'm praying for {victim}.", "Shh. I'm praying {victim} balances.")
rep(mp, "Peace be on this village.", "Peace be on these markets.")
rep(mp, "Master says never touch the forge bare-handed.", "Master says never quote a price unchecked.")
rep(mp, "Forty-two nails today. Forty-three.", "Forty-two quotes today. Forty-three.")
rep(mp, "Mind the stone, it bites.", "Mind the data, it bites.")
rep(mp, "Flour gets everywhere. Everywhere.", "Noise gets everywhere. Everywhere.")
rep("js/VillageScene.js", 'title: "Vaudville"', 'title: "Tickerville"')

fails = 0
for f, old, new, n in R:
    path = ROOT + f
    text = open(path, encoding="utf-8").read()
    if old.startswith("RE:"):
        pat = old[3:]
        got = len(re.findall(pat, text))
        if got == n:
            text = re.sub(pat, lambda _m: new, text)
    else:
        got = text.count(old)
        if got == n:
            text = text.replace(old, new)
    if got != n:
        print(f"MISMATCH {f}: {old[:60]!r} found {got}, expected {n}")
        fails += 1
        continue
    open(path, "w", encoding="utf-8").write(text)
print("done, mismatches:", fails)
sys.exit(1 if fails else 0)
