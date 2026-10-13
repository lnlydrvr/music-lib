/* wordDiff: пословный diff для Picard-стиля «было → стало». */

export interface DiffPart {
  t: string;
  del?: boolean;
  add?: boolean;
}

export interface WordDiff {
  oldParts: DiffPart[];
  newParts: DiffPart[];
}

function tokenize(v: string): string[] {
  return String(v || "")
    .split(/(\s+)/)
    .filter((s) => s !== "");
}

export function wordDiff(oldV: unknown, newV: unknown): WordDiff {
  const a = tokenize(String(oldV || ""));
  const b = tokenize(String(newV || ""));
  const n = a.length;
  const m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const oldParts: DiffPart[] = [];
  const newParts: DiffPart[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      oldParts.push({ t: a[i] });
      newParts.push({ t: b[j] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      oldParts.push({ t: a[i], del: true });
      i++;
    } else {
      newParts.push({ t: b[j], add: true });
      j++;
    }
  }
  while (i < n) {
    oldParts.push({ t: a[i], del: true });
    i++;
  }
  while (j < m) {
    newParts.push({ t: b[j], add: true });
    j++;
  }
  return { oldParts, newParts };
}
