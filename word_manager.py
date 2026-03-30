from collections import Counter
import threading


class WordManager:
    def __init__(self):
        self._counts: Counter = Counter()
        self._lock = threading.Lock()

    def add_word(self, word: str) -> int:
        word = word.strip().lower()
        if not word:
            return 0
        with self._lock:
            self._counts[word] += 1
            return self._counts[word]

    def get_top_words(self, n: int = 20) -> list[dict]:
        with self._lock:
            top = self._counts.most_common(n)
        if not top:
            return []

        max_count = top[0][1]
        min_count = top[-1][1]
        count_range = max(max_count - min_count, 1)

        MIN_SIZE = 20
        MAX_SIZE = 120

        result = []
        for text, count in top:
            # Map count to font size range
            normalized = (count - min_count) / count_range
            size = int(MIN_SIZE + normalized * (MAX_SIZE - MIN_SIZE))
            result.append({"text": text, "size": size, "count": count})

        return result

    def get_all_words(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def total_submissions(self) -> int:
        with self._lock:
            return sum(self._counts.values())

    def reset(self):
        with self._lock:
            self._counts.clear()
