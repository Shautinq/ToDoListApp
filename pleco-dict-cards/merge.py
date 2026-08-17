# -*- coding: utf-8 -*-
"""
Merge the 9 bkrs_NN.pqb parts (from pleco-dict/) back into one single
bkrs_merged.pqb Pleco dictionary. Pure Python stdlib only - no pip install
needed, runs fine under plain Termux `python`.

Usage (from inside the pleco-dict folder, next to bkrs_01.pqb ... bkrs_09.pqb):
    python merge.py

Produces bkrs_merged.pqb (~680 MB) in the same folder. Add just that ONE
file to Pleco instead of all 9 parts.
"""
import glob
import os
import sqlite3
import sys
import time

import glob as _glob
OUT = 'bkrs_merged.pqb' if _glob.glob('bkrs_[0-9][0-9].pqb') else 'bkrs_short_merged.pqb'


def create_db(path):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    c = conn.cursor()
    created = str(int(time.time()))
    c.execute('CREATE TABLE pleco_dict_properties ("propset" INTEGER, "propid" TEXT, "propvalue" TEXT, "propisstring" INTEGER, UNIQUE ("propset", "propid") )')
    props = [
        (0, 'FormatString', 'Pleco SQL Dictionary Database', 1),
        (0, 'FormatVersion', '8', 0),
        (0, 'FileGenerator', 'Pleco Engine 2.0', 1),
        (0, 'FilePlatform', 'Android', 1),
        (0, 'FileCreated', created, 0),
        (0, 'FileCreator', '16796996', 0),
        (0, 'FileID', '-1530540358', 0),
        (0, 'DictMenuName', 'БКРС Карточки' if 'short' in OUT else 'БКРС Ch-Ru', 1),
        (0, 'DictShortName', 'БКРСк' if 'short' in OUT else 'БКРС', 1),
        (0, 'DictName', ('BKRS short (flashcards)' if 'short' in OUT else 'BKRS Chinese-Russian Dictionary'), 1),
        (0, 'DictLang', 'Chinese', 1),
        (0, 'TransLang', 'Russian', 1),
        (0, 'EditLock', '1', 0),
        (0, 'SortMethod', None, 0),
        (0, 'NoSortKey', None, 0),
        (0, 'DictIconName', 'БКР', 1),
        (0, 'DictIconFillColor', '39372', 0),
        (0, 'DictIconTextColor', '16777215', 0),
    ]
    c.executemany('INSERT INTO pleco_dict_properties VALUES (?,?,?,?)', props)
    c.execute('CREATE TABLE pleco_dict_entries ("uid" INTEGER PRIMARY KEY AUTOINCREMENT, "created" INTEGER, "modified" INTEGER, "length" INTEGER, "word" TEXT COLLATE NOCASE, "altword" TEXT COLLATE NOCASE, "pron" TEXT COLLATE NOCASE, "defn" TEXT, "sortkey" TEXT UNIQUE);')
    for t in ('hz', 'py'):
        c.execute(f'CREATE TABLE "pleco_dict_posdex_{t}_1" ("syllable" TEXT COLLATE NOCASE, "uid" INTEGER, "length" INTEGER);')
        for i in (2, 3, 4):
            c.execute(f'CREATE TABLE "pleco_dict_posdex_{t}_{i}" ("syllable" TEXT COLLATE NOCASE, "uid" INTEGER);')
    conn.commit()
    return conn, c


def add_entry(c, seen_sortkeys, word, altword, pron, defn):
    wordlen = len(word)
    syls = pron.split() if pron else []
    first_pron = syls[0] if syls else ''
    sortkey = first_pron + word
    if sortkey in seen_sortkeys:
        n = 2
        while f'{sortkey}\x00{n}' in seen_sortkeys:
            n += 1
        sortkey = f'{sortkey}\x00{n}'
    seen_sortkeys.add(sortkey)
    ctime = str(int(time.time()))
    c.execute(
        'INSERT INTO pleco_dict_entries VALUES (NULL,?,?,?,?,?,?,?,?)',
        (ctime, ctime, wordlen, word, altword, pron, defn, sortkey))
    uid = c.lastrowid

    chars = list(word)
    for pos, ch in enumerate(chars[:4], start=1):
        if pos == 1:
            c.execute('INSERT INTO pleco_dict_posdex_hz_1 VALUES (?,?,?)', (ch, uid, wordlen))
        else:
            c.execute(f'INSERT INTO pleco_dict_posdex_hz_{pos} VALUES (?,?)', (ch, uid))

    if syls and len(syls) == len(chars):
        for pos, syl in enumerate(syls[:4], start=1):
            if pos == 1:
                c.execute('INSERT INTO pleco_dict_posdex_py_1 VALUES (?,?,?)', (syl, uid, wordlen))
            else:
                c.execute(f'INSERT INTO pleco_dict_posdex_py_{pos} VALUES (?,?)', (syl, uid))


def finish(conn, c):
    c.execute('CREATE INDEX idx_hz1 ON pleco_dict_posdex_hz_1 ("syllable","uid","length");')
    c.execute('CREATE INDEX idx_hz1u ON pleco_dict_posdex_hz_1 (uid);')
    c.execute('CREATE INDEX idx_py1 ON pleco_dict_posdex_py_1 ("syllable","uid","length");')
    c.execute('CREATE INDEX idx_py1u ON pleco_dict_posdex_py_1 (uid);')
    for i in (2, 3, 4):
        c.execute(f'CREATE INDEX idx_hz{i} ON pleco_dict_posdex_hz_{i} ("syllable","uid");')
        c.execute(f'CREATE INDEX idx_hz{i}u ON pleco_dict_posdex_hz_{i} (uid);')
        c.execute(f'CREATE INDEX idx_py{i} ON pleco_dict_posdex_py_{i} ("syllable","uid");')
        c.execute(f'CREATE INDEX idx_py{i}u ON pleco_dict_posdex_py_{i} (uid);')
    conn.commit()
    conn.close()


def main():
    parts = sorted(glob.glob('bkrs_[0-9][0-9].pqb')) or sorted(glob.glob('bkrs_short_[0-9][0-9].pqb'))
    if not parts:
        print('No bkrs_NN.pqb files found in this folder. Run this script '
              'from inside pleco-dict/ (next to bkrs_01.pqb ... bkrs_09.pqb).')
        sys.exit(1)
    print(f'Found {len(parts)} parts: {", ".join(parts)}')

    conn, c = create_db(OUT)
    seen = set()
    total = 0
    t0 = time.time()
    for part in parts:
        src = sqlite3.connect(part)
        src.text_factory = str
        n_part = 0
        for word, altword, pron, defn in src.execute(
                'select word, altword, pron, defn from pleco_dict_entries order by uid'):
            add_entry(c, seen, word, altword or '', pron or '', defn)
            n_part += 1
            total += 1
            if total % 100000 == 0:
                conn.commit()
                print(f'  {total:,} entries merged... ({time.time()-t0:.0f}s)', flush=True)
        src.close()
        print(f'{part}: {n_part:,} entries added', flush=True)

    print('Building search indexes (this takes a while, be patient)...', flush=True)
    finish(conn, c)
    size_mb = os.path.getsize(OUT) / 1048576
    print(f'DONE: {OUT} - {total:,} entries, {size_mb:.1f} MB, {time.time()-t0:.0f}s total')
    print('Now add ONLY this one file to Pleco (Manage Dictionaries -> Add User -> Add Existing).')


if __name__ == '__main__':
    main()
