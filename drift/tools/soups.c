/* soups: run random 16x16 soups and print the objects that escape from them.
 *
 *   soups TABLE SEED SECONDS
 *
 * TABLE is 512 characters '0'/'1': the next state for each 3x3 window, index
 * 256*NW + 128*N + 64*NE + 32*W + 16*C + 8*E + 4*SW + 2*S + SE (driftlib's
 * order). Each soup runs for GENS generations on a GRID x GRID torus. Every
 * clump of live cells (cells within 2 of each other) that has moved clear of
 * the soup's box and is a spaceship (it comes back to its own shape, moved,
 * within 16 gens) is printed as one line "cells: r,c r,c ...", relative to its
 * top-left. The last line is "soups N".
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define GRID 192
#define GENS 160
#define SOUP 16
#define MAXOBJ 60

static unsigned char T[512], a[GRID][GRID], b[GRID][GRID], seen[GRID][GRID];
static unsigned long long rng;

static unsigned rnd(void) {
  rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
  return (unsigned)(rng >> 32);
}

static void step(void) {
  for (int r = 0; r < GRID; r++) {
    int ru = (r + GRID - 1) % GRID, rd = (r + 1) % GRID;
    for (int c = 0; c < GRID; c++) {
      int cl = (c + GRID - 1) % GRID, cr = (c + 1) % GRID;
      int k = a[ru][cl] << 8 | a[ru][c] << 7 | a[ru][cr] << 6 | a[r][cl] << 5 | a[r][c] << 4 |
              a[r][cr] << 3 | a[rd][cl] << 2 | a[rd][c] << 1 | a[rd][cr];
      b[r][c] = T[k];
    }
  }
  memcpy(a, b, sizeof a);
}

/* Does this object move and come back to its own shape within 16 gens? */
#define OB 64
static unsigned char oa[OB][OB], ob[OB][OB];
static void norm(unsigned char g[OB][OB], int *n, int *r0, int *c0) {
  *n = 0; *r0 = OB; *c0 = OB;
  for (int r = 0; r < OB; r++)
    for (int c = 0; c < OB; c++)
      if (g[r][c]) { (*n)++; if (r < *r0) *r0 = r; if (c < *c0) *c0 = c; }
}
static int isship(int *qr, int *qc, int n, int r0, int c0) {
  static unsigned char first[OB][OB];
  memset(oa, 0, sizeof oa);
  for (int i = 0; i < n; i++) oa[qr[i] - r0 + 22][qc[i] - c0 + 22] = 1;
  memcpy(first, oa, sizeof oa);
  for (int g = 1; g <= 16; g++) {
    memset(ob, 0, sizeof ob);
    for (int r = 1; r < OB - 1; r++)
      for (int c = 1; c < OB - 1; c++) {
        int k = oa[r-1][c-1] << 8 | oa[r-1][c] << 7 | oa[r-1][c+1] << 6 | oa[r][c-1] << 5 | oa[r][c] << 4 |
                oa[r][c+1] << 3 | oa[r+1][c-1] << 2 | oa[r+1][c] << 1 | oa[r+1][c+1];
        ob[r][c] = T[k];
      }
    memcpy(oa, ob, sizeof oa);
    int m, a0, b0;
    norm(oa, &m, &a0, &b0);
    if (m == 0 || m > 4 * n + 20 || a0 < 2 || b0 < 2) return 0;
    for (int r = 0; r < OB; r++)
      for (int c = 0; c < OB; c++)
        if (oa[r][c] && (r > OB - 3 || c > OB - 3)) return 0;
    if (m != n || (a0 == 22 && b0 == 22)) continue;
    int same = 1;
    for (int r = 0; r + a0 < OB && r + 22 < OB && same; r++)
      for (int c = 0; c + b0 < OB && c + 22 < OB; c++)
        if (oa[r + a0][c + b0] != first[r + 22][c + 22]) { same = 0; break; }
    if (same) return 1;
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 4 || strlen(argv[1]) != 512) {
    fprintf(stderr, "usage: soups TABLE(512 chars 0/1) SEED SECONDS\n");
    return 1;
  }
  for (int i = 0; i < 512; i++) T[i] = argv[1][i] == '1';
  if (T[0]) { printf("soups 0\n"); return 0; }   /* B0: no empty background */
  rng = 0x9e3779b97f4a7c15ULL ^ (unsigned long long)atoll(argv[2]) * 0x2545F4914F6CDD1DULL;
  double limit = atof(argv[3]);
  clock_t t0 = clock();
  long soups = 0;
  int lo = (GRID - SOUP) / 2, hi = lo + SOUP - 1, pad = 6;
  static int qr[GRID * GRID], qc[GRID * GRID];
  while ((double)(clock() - t0) / CLOCKS_PER_SEC < limit) {
    memset(a, 0, sizeof a);
    for (int r = lo; r <= hi; r++)
      for (int c = lo; c <= hi; c++) a[r][c] = rnd() >> 31;
    soups++;
    int pop = 0;
    for (int g = 0; g < GENS; g++) {
      step();
      if ((g & 15) == 15) {
        pop = 0;
        for (int r = 0; r < GRID; r++)
          for (int c = 0; c < GRID; c++) pop += a[r][c];
        if (pop == 0 || pop > GRID * GRID / 8) break;
      }
    }
    if (pop == 0 || pop > GRID * GRID / 8) continue;
    memset(seen, 0, sizeof seen);
    for (int r = 2; r < GRID - 2; r++)
      for (int c = 2; c < GRID - 2; c++) {
        if (!a[r][c] || seen[r][c]) continue;
        int n = 0, h = 0, r0 = r, r1 = r, c0 = c, c1 = c, edge = 0;
        qr[n] = r; qc[n] = c; n++; seen[r][c] = 1;
        while (h < n) {
          int y = qr[h], x = qc[h]; h++;
          for (int dy = -2; dy <= 2; dy++)
            for (int dx = -2; dx <= 2; dx++) {
              int yy = y + dy, xx = x + dx;
              if (yy < 0 || yy >= GRID || xx < 0 || xx >= GRID) { edge = 1; continue; }
              if (a[yy][xx] && !seen[yy][xx]) {
                seen[yy][xx] = 1;
                qr[n] = yy; qc[n] = xx; n++;
                if (yy < r0) r0 = yy; if (yy > r1) r1 = yy;
                if (xx < c0) c0 = xx; if (xx > c1) c1 = xx;
              }
            }
        }
        if (edge || n > MAXOBJ) continue;
        if (r1 >= lo - pad && r0 <= hi + pad && c1 >= lo - pad && c0 <= hi + pad) continue;
        if (r1 - r0 >= 20 || c1 - c0 >= 20 || !isship(qr, qc, n, r0, c0)) continue;
        printf("cells:");
        for (int i = 0; i < n; i++) printf(" %d,%d", qr[i] - r0, qc[i] - c0);
        printf("\n");
      }
  }
  printf("soups %ld\n", soups);
  return 0;
}
