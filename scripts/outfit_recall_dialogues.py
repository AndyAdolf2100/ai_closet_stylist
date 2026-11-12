"""Synthetic dialogue expectations shared by offline and explicit live recall checks."""
CASES = [
    ('我刚才第一套搭配是啥来着', [1]),
    ('输出一下', [1]),
    ('第一个给我看看', [1]),
    ('第三个再发我一下', [3]),
    ('最后一个给我看看', [5]),
    ('倒数第二个给我看看', [4]),
    ('第一套和第三套都发我看看', [1, 3]),
    ('Show me the first outfit again', [1]),
    ('Show me the third look', [3]),
    ('Show me the last outfit', [5]),
    ('Show me the second-to-last outfit', [4]),
    ('把第1套、第3套再给我看看', [1, 3]),
    ('把第一套再发我看看', [1]),
    ('看看第1套', [1]),
    ('最早那套再给我看看', [1]),
]
