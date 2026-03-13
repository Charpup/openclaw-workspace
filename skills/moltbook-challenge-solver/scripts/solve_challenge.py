#!/usr/bin/env python3
import argparse
import re

NUM = {
    'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,
    'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,
    'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90,'hundred':100
}


def dedup_letters_only(s: str) -> str:
    out=[]; prev=''
    for ch in s:
        if ch.isalpha():
            if prev and prev.lower()==ch.lower():
                continue
            out.append(ch.lower()); prev=ch
    return ''.join(out)

# Accept both normal and deduped word forms (e.g., three -> thre)
NUM_ALIASES = dict(NUM)
for k, v in list(NUM.items()):
    dk = dedup_letters_only(k)
    NUM_ALIASES[dk] = v

NUM_KEYS = sorted(NUM_ALIASES.keys(), key=len, reverse=True)


def deobf(text: str) -> str:
    out = []
    prev = ''
    for ch in text:
        if ch.isalpha():
            if prev and prev.lower() == ch.lower():
                continue
            out.append(ch.lower())
            prev = ch
        else:
            out.append(ch)
            prev = ''
    return ''.join(out)


def words_to_number(words):
    cur = 0
    for w in words:
        if w not in NUM_ALIASES:
            continue
        if NUM_ALIASES[w] == 100:
            cur = max(1, cur) * 100
        else:
            cur += NUM_ALIASES[w]
    return float(cur)


def parse_wordstream_to_words(letters_only: str):
    words = []
    i = 0
    n = len(letters_only)
    while i < n:
        matched = None
        for k in NUM_KEYS:
            if letters_only.startswith(k, i):
                matched = k
                break
        if matched:
            words.append(matched)
            i += len(matched)
        else:
            i += 1
    return words


def phrase_to_num(phrase: str):
    ds = re.findall(r'-?\d+(?:\.\d+)?', phrase)
    if ds:
        return float(ds[0])

    letters = ''.join(ch for ch in phrase.lower() if ch.isalpha())
    words = parse_wordstream_to_words(letters)
    if not words:
        raise ValueError(f'cannot parse number from phrase: {phrase}')
    return words_to_number(words)


def detect_op(s: str):
    if any(k in s for k in ['product', 'times', 'multiply']):
        return '*'
    if any(k in s for k in ['difference', 'minus', 'subtract', 'decrease by']):
        return '-'
    if any(k in s for k in ['quotient', 'divide']):
        return '/'
    if any(k in s for k in ['sum', 'plus', 'add', 'increases by', 'increase by']):
        return '+'
    # tolerate obfuscated separators: "slow s down by"
    if re.search(r'slow\W*s?\W*down\W*by', s):
        return '-'
    return '+'


def solve(challenge: str):
    s = deobf(challenge)
    sl = s.lower()
    op = detect_op(sl)

    # Pattern A: "product/sum/difference/quotient of X and Y"
    m = re.search(r'(?:of|between)\s+(.+?)\s+and\s+(.+?)(?:\?|\.|$)', sl)
    if m:
        a = phrase_to_num(m.group(1))
        b = phrase_to_num(m.group(2))
    else:
        # Pattern B: velocity style - "at X ... meter ... slow(s) down by Y"
        m_at = re.search(r'at\W+(.+?)\W+meter', sl)
        m_by = re.search(r'by\W+(.+?)(?:\W+what|\?|\.|$)', sl)

        # Pattern C: force semantics
        # C1) multiplication: "force is X newtons ... force Y times"
        m_force_base = re.search(r'is\W+(.+?)\W+n\w*to\w*s', sl)
        m_force_times = re.search(r'exerts\W+force\W+(.+?)\W+times', sl)

        # C1.5) multiplication: "... X newtons ... has Y claws ... total force"
        m_force_of = re.search(r'force\W+of\W+(.+?)\W+n\w*to\w*s', sl)
        m_has_claws = re.search(r'has\W+(.+?)\W+claws?', sl)
        m_newtons_any = re.search(r'(.+?)\W+n\w*to\w*s', sl)
        has_total_force = bool(re.search(r'total\W*fo\W*r\W*c\W*e|total\W*force', sl))

        # C2) additive total force: two claw forces in newtons
        force_vals = []
        for seg in re.findall(r'exerts\W+(.+?)\W+n\w*to\w*s', sl):
            try:
                force_vals.append(phrase_to_num(seg))
            except Exception:
                pass
        if m_force_base:
            try:
                force_vals.insert(0, phrase_to_num(m_force_base.group(1)))
            except Exception:
                pass

        if m_force_base and m_force_times and (has_total_force or 'times' in sl):
            a = phrase_to_num(m_force_base.group(1))
            b = phrase_to_num(m_force_times.group(1))
            op = '*'
        elif m_force_of and m_has_claws and has_total_force:
            a = phrase_to_num(m_force_of.group(1))
            b = phrase_to_num(m_has_claws.group(1))
            op = '*'
        elif m_newtons_any and m_has_claws and has_total_force:
            a = phrase_to_num(m_newtons_any.group(1))
            b = phrase_to_num(m_has_claws.group(1))
            op = '*'
        elif (has_total_force or 'another claw' in sl) and len(force_vals) >= 2:
            a, b = force_vals[0], force_vals[1]
            op = '+'
        elif m_at and m_by and op in ['+', '-']:
            a = phrase_to_num(m_at.group(1))
            b = phrase_to_num(m_by.group(1))
        else:
            # Pattern D fallback: parse full letter stream and take last two numbers
            words = parse_wordstream_to_words(''.join(ch for ch in sl if ch.isalpha()))
            vals = [float(NUM_ALIASES[w]) for w in words]
            nums = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', sl)]
            merged = vals + nums
            if len(merged) < 2:
                raise ValueError('unable to parse enough operands')
            a, b = merged[-2], merged[-1]

    if op == '*':
        r = a * b
    elif op == '-':
        r = a - b
    elif op == '/':
        r = a / b if b else 0
    else:
        r = a + b
    return f'{r:.2f}'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--challenge', required=True)
    args = ap.parse_args()
    print(solve(args.challenge))
