// Port of the dr2.c search (Dean Hickerson, 1997; DONTCHECK cells added 2014).
// Function names and structure follow dr2.c so the two can be read side by
// side; comments mark the places where behaviour intentionally differs.
#include "search.h"

#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

namespace drift {

static const bool OK = false, ERR = true;
enum { STATOR = 2, CONN = 3 };   // extra values in the rotor scratch grid

static std::string fmt(const char *f, ...) __attribute__((format(printf, 1, 2)));
static std::string fmt(const char *f, ...) {
  char buf[512];
  va_list ap;
  va_start(ap, f);
  vsnprintf(buf, sizeof buf, f, ap);
  va_end(ap);
  return buf;
}

/************************************************************************/
/* Regions                                                              */
/************************************************************************/

bool parseRegion(const std::string &str, Region &reg, char def, std::string &err) {
  const char *p = str.c_str();
  while (*p == ' ') p++;
  reg.type = *p;
  if (isdigit((unsigned char)*p) || *p == '-') reg.type = def;
  else p++;

  switch (reg.type) {
    case 'p':
      if (sscanf(p, "%d %d", &reg.r0, &reg.c0) != 2) { err = "bad point region: " + str; return false; }
      reg.minrow = reg.maxrow = reg.r0;
      reg.mincol = reg.maxcol = reg.c0;
      break;
    case 'l':
    case 'r':
      if (sscanf(p, "%d %d %d %d", &reg.r0, &reg.c0, &reg.r1, &reg.c1) != 4) {
        err = "bad line/rectangle region: " + str;
        return false;
      }
      reg.minrow = std::min(reg.r0, reg.r1);
      reg.mincol = std::min(reg.c0, reg.c1);
      reg.maxrow = std::max(reg.r0, reg.r1);
      reg.maxcol = std::max(reg.c0, reg.c1);
      break;
    case 't':
      if (sscanf(p, "%d %d %d %d %d %d", &reg.r0, &reg.c0, &reg.r1, &reg.c1, &reg.r2, &reg.c2) != 6) {
        err = "bad triangle region: " + str;
        return false;
      }
      reg.orient = (long)reg.r0 * (reg.c1 - reg.c2) + (long)reg.r1 * (reg.c2 - reg.c0) +
                   (long)reg.r2 * (reg.c0 - reg.c1);
      if (reg.orient == 0) { err = "degenerate triangle region: " + str; return false; }
      reg.minrow = std::min(reg.r0, std::min(reg.r1, reg.r2));
      reg.maxrow = std::max(reg.r0, std::max(reg.r1, reg.r2));
      reg.mincol = std::min(reg.c0, std::min(reg.c1, reg.c2));
      reg.maxcol = std::max(reg.c0, std::max(reg.c1, reg.c2));
      break;
    default:
      err = "bad region type: " + str;
      return false;
  }
  return true;
}

void Region::shift(int dr, int dc) {
  r0 += dr; r1 += dr; r2 += dr; minrow += dr; maxrow += dr;
  c0 += dc; c1 += dc; c2 += dc; mincol += dc; maxcol += dc;
  if (type == 't')
    orient = (long)r0 * (c1 - c2) + (long)r1 * (c2 - c0) + (long)r2 * (c0 - c1);
}

bool Region::contains(int row, int col) const {
  if (row < minrow || row > maxrow || col < mincol || col > maxcol) return false;
  switch (type) {
    case 'p':
    case 'r': return true;
    case 'l': return (long)r0 * (c1 - col) + (long)r1 * (col - c0) + (long)row * (c0 - c1) == 0;
    case 't':
      return orient * ((long)r0 * (c1 - col) + (long)r1 * (col - c0) + (long)row * (c0 - c1)) >= 0 &&
             orient * ((long)r0 * (col - c2) + (long)row * (c2 - c0) + (long)r2 * (c0 - col)) >= 0 &&
             orient * ((long)row * (c1 - c2) + (long)r1 * (c2 - col) + (long)r2 * (col - c1)) >= 0;
  }
  return false;
}

/************************************************************************/
/* Known rotors                                                         */
/************************************************************************/

// Same format as dr2.c's readknownrotors(): a descriptor (newlines inside it
// are dropped), one or more tabs, then a name ending at the newline.
bool KnownRotors::load(const std::string &path, std::string &err) {
  FILE *f = fopen(path.c_str(), "r");
  if (!f) { err = "can't open known rotors file '" + path + "'"; return false; }
  std::string desc, name;
  bool readingname = false;
  int ch;
  auto finish = [&]() {
    if (!index.count(desc)) index[desc] = (int)names.size();
    names.push_back(name);
    desc.clear();
    name.clear();
  };
  while ((ch = fgetc(f)) != EOF) {
    if (ch == '\t') { readingname = true; name.clear(); }
    else if (ch == '\n') {
      if (readingname) { finish(); readingname = false; }
    } else if (readingname) name += (char)ch;
    else desc += (char)ch;
  }
  if (readingname) finish();
  fclose(f);
  return true;
}

/************************************************************************/
/* Setup                                                                */
/************************************************************************/

int Search::myrandom(int n) {   // Kernighan & Ritchie rand(), as in dr2.c
  rng = rng * 1103515245 + 12345;
  return (int)((unsigned int)(rng / 65536) % 32768) % n;
}

void Search::initarrays() {
  for (int r = -2; r < HT + 2; r++)
    for (int c = -2; c < WD + 2; c++) {
      int i = idx(r, c);
      bool inside = r >= 0 && r < HT && c >= 0 && c < WD;
      if (!inside || r <= 1 || r >= HT - 2 || c <= 1 || c >= WD - 2) {
        bkgd[i] = curr[i] = OFF;
        flag[i] = inside && P.checkBorder ? 0xFF & ~DONTCHECK : 0xFF;
      } else {
        bkgd[i] = curr[i] = UNK;
        flag[i] = 0;
      }
    }
  for (int r = -1; r <= HT; r++)
    for (int c = -1; c <= WD; c++) {
      int i = idx(r, c), x = 0;
      for (int k = 0; k < 9; k++) x += bkgd[i + OFFS[k]] * POW3[k];
      code[i] = (uint16_t)x;
    }
}

void Search::init(const Params &p, const Rule *r, const KnownRotors *k) {
  P = p;
  rule = r;
  known = k;
  HT = P.HT;
  WD = P.WD;
  if (HT < 5 || WD < 5) throw std::runtime_error("space must be at least 5x5");
  S = WD + 4;
  int N = (HT + 4) * S;
  for (int k2 = 0; k2 < 9; k2++) OFFS[k2] = DR[k2] * S + DC[k2];
  bkgd.assign(N, OFF);
  curr.assign(N, OFF);
  flag.assign(N, 0xFF);
  code.assign(N, 0);
  stamp.assign(N, 0);
  cell.assign(N, STATOR);
  st.assign((size_t)HT * WD * 8 + 64, Setting{});
  chglist.assign(4096, Pt{0, 0});
  int G = P.maxgen + 2;
  chgd.assign(G, 0);
  nays.assign(G, 0);
  chgcount.assign(G, 0);
  agesm.assign(G, 0);
  width.assign(G, 0);
  height.assign(G, 0);
  ulist.clear();
  rng = P.seed;
  initarrays();
  nwstng = 0;
  chgd[0] = nays[0] = 0;

  for (const PatternOp &op : P.ops) {
    switch (op.kind) {
      case PatternOp::READ:
        readpattern(op);
        break;
      case PatternOp::CLEAR:
      case PatternOp::SETFLAG:
      case PatternOp::CLEARFLAG: {
        Region reg = op.reg;
        reg.minrow = std::max(reg.minrow, 0);
        reg.maxrow = std::min(reg.maxrow, HT - 1);
        reg.mincol = std::max(reg.mincol, 0);
        reg.maxcol = std::min(reg.maxcol, WD - 1);
        for (int rr = reg.minrow; rr <= reg.maxrow; rr++)
          for (int cc = reg.mincol; cc <= reg.maxcol; cc++) {
            if (!reg.contains(rr, cc)) continue;
            int i = idx(rr, cc);
            if (op.kind == PatternOp::CLEAR) {
              if (bkgd[i] == UNK && proceed(rr, cc, OFF, false, false) == ERR)
                throw std::runtime_error(fmt("clearing the region makes the background "
                                             "unstable at row %d, col %d", rr, cc));
            } else if (op.kind == PatternOp::SETFLAG)
              flag[i] |= 1 << op.bit;
            else
              flag[i] &= ~(1 << op.bit);
          }
        break;
      }
    }
  }
}

// dr2.c's readpattern(). Difference: DONTCHECK cells from several read
// commands accumulate (dr2.c restarts its list on each read and also appends
// a stray (0,0) entry to it).
void Search::readpattern(const PatternOp &op) {
  int r = op.r, c = op.c;
  auto addflags = [&](char ch) {
    if (r < 0 || r >= HT || c < 0 || c >= WD) return;
    int i = idx(r, c);
    if (ch == ':' || ch == 'O' || ch == 's') flag[i] |= DONTCHANGE;
    if (P.var[127] && strchr(".o01?234", ch)) flag[i] |= DONTCOUNT;
    if (ch == '2' || ch == '3' || ch == '4') flag[i] |= DONTCHECK;
    if (flag[i] & DONTCHECK) {
      for (const Pt &u : ulist)
        if (u.r == r && u.c == c) return;
      ulist.push_back({r, c});
    }
  };
  for (const std::string &line : op.lines) {
    for (char ch : line) {
      if (ch == '\r') continue;
      addflags(ch);
      int bg, cr;
      switch (ch) {
        case '.': case ':': case '2': bg = 0; cr = 0; break;
        case 'o': case 'O': case '3': bg = 1; cr = 1; break;
        case '0': bg = 1; cr = 0; break;
        case '1': bg = 0; cr = 1; break;
        case ',': case '?': case 's': case '4': c++; continue;
        case '!': return;
        default:
          throw std::runtime_error(fmt("bad character '%c' in pattern", ch));
      }
      if (r < 0 || r >= HT || c < 0 || c >= WD)
        throw std::runtime_error(fmt("pattern cell at row %d, col %d is outside the %dx%d space",
                                     r, c, HT, WD));
      int i = idx(r, c);
      if (bkgd[i] == (1 ^ bg) || (bkgd[i] == UNK && proceed(r, c, bg, false, false) == ERR))
        throw std::runtime_error(fmt("pattern background is not stable at row %d, col %d", r, c));
      if (bg != cr) {
        ensure(nays[0]);
        chglist[nays[0]++] = {r, c};
      }
      c++;
    }
    addflags('\n');
    r++;
    c = op.c;
  }
}

/************************************************************************/
/* Keeping the background stable                                        */
/************************************************************************/

void Search::set1(int r, int c, uint8_t v) {
  int i = idx(r, c);
  int d = (int)v - (int)bkgd[i];
  bkgd[i] = curr[i] = v;
  Setting &s = st[nwstng];
  s.r = r;
  s.c = c;
  s.val = v;
  if (d)
    for (int k = 0; k < 9; k++) code[i - OFFS[k]] = (uint16_t)(code[i - OFFS[k]] + d * POW3[k]);
}

void Search::setbkgd(int r, int c, uint8_t v, bool f, bool dec) {
  if (bkgd[idx(r, c)] != UNK || r == 0 || r == HT - 1 || c == 0 || c == WD - 1)
    throw std::runtime_error(fmt("internal error: setbkgd(%d,%d) on a known cell", r, c));
  auto push = [&](bool fr, bool de) {
    Setting &s = st[nwstng++];
    s.free = fr;
    s.decision = de;
    s.donated = false;
  };
  set1(r, c, v);
  push(f, dec);

  // As in dr2.c, a cell that maps to itself gets a duplicate setting.
  const long *var = P.var;
  switch (P.symm) {
    case NOSYMM:
      break;
    case HORSYMM:
      if (var[130]) v = 1 - v;
      if (c >= var[114]) { set1(HT - 1 - r, c, v); push(0, 0); }
      break;
    case VERTSYMM:
      if (var[130]) v = 1 - v;
      if (r >= var[115]) { set1(r, WD - 1 - c, v); push(0, 0); }
      break;
    case DIAGSYMM:
      set1(c, r, v); push(0, 0);
      break;
    case ROT90SYMM:
      set1(HT - 1 - c, r, v); push(0, 0);
      set1(HT - 1 - r, HT - 1 - c, v); push(0, 0);
      set1(c, HT - 1 - r, v); push(0, 0);
      break;
    case ROT180SYMM:
      if (var[130]) v = 1 - v;
      set1(HT - 1 - r, WD - 1 - c, v); push(0, 0);
      break;
    case PLUSSYMM:
      set1(HT - 1 - r, c, v); push(0, 0);
      set1(HT - 1 - r, WD - 1 - c, v); push(0, 0);
      set1(r, WD - 1 - c, v); push(0, 0);
      break;
    case XSYMM:
      set1(c, r, v); push(0, 0);
      set1(HT - 1 - r, HT - 1 - c, v); push(0, 0);
      set1(HT - 1 - c, HT - 1 - r, v); push(0, 0);
      break;
    case FULLSYMM:
      set1(r, HT - 1 - c, v); push(0, 0);
      set1(HT - 1 - r, c, v); push(0, 0);
      set1(HT - 1 - r, HT - 1 - c, v); push(0, 0);
      set1(c, r, v); push(0, 0);
      set1(c, HT - 1 - r, v); push(0, 0);
      set1(HT - 1 - c, r, v); push(0, 0);
      set1(HT - 1 - c, HT - 1 - r, v); push(0, 0);
      break;
  }
}

// One table lookup replaces dr2.c's consistable switch. For outer-totalistic
// rules the forced cells are exactly the ones dr2.c forces (its table is
// already complete for a symmetric count constraint); for INT/MAP rules each
// unknown neighbour can be forced individually.
bool Search::forceCells(int r, int c, int i, uint32_t e) {
  if (e & CONS_BAD) return ERR;
  for (uint32_t m = e & 0x3ffff; m; m &= m - 1) {
    int b = __builtin_ctz(m), k = b < 9 ? b : b - 9;
    if (bkgd[i + OFFS[k]] == UNK) setbkgd(r + DR[k], c + DC[k], b < 9 ? ON : OFF, 0, 0);
  }
  return OK;
}

// consistify() on (r,c) and its neighbours, in dr2.c's order, with the usual
// "nothing forced" case done inline.
bool Search::consis9(int r, int c) {
  static const int ORDER[9][2] = {{0, 0}, {-1, 0}, {0, -1}, {1, 0}, {0, 1},
                                  {-1, -1}, {1, -1}, {-1, 1}, {1, 1}};
  const uint32_t *cons = rule->cons3;
  int i0 = idx(r, c);
  for (int n = 0; n < 9; n++) {
    int i = i0 + ORDER[n][0] * S + ORDER[n][1];
    uint32_t e = cons[code[i]];
    if (!e || (flag[i] & DONTCHECK)) continue;
    if (forceCells(r + ORDER[n][0], c + ORDER[n][1], i, e)) return ERR;
  }
  return OK;
}

bool Search::proceed(int r, int c, uint8_t v, bool f, bool dec) {
  nxstng = nwstng;
  setbkgd(r, c, v, f, dec);
  while (nxstng != nwstng)
    if (consis9(st[nxstng].r, st[nxstng].c)) return ERR;
    else nxstng++;
  return OK;
}

bool Search::backup() {
  while (nwstng > 0) {
    nwstng--;
    const Setting &s = st[nwstng];
    int i = idx(s.r, s.c);
    int d = (int)UNK - (int)bkgd[i];
    bkgd[i] = UNK;
    curr[i] = UNK;
    if (d)
      for (int k = 0; k < 9; k++) code[i - OFFS[k]] = (uint16_t)(code[i - OFFS[k]] + d * POW3[k]);
    if (s.free) return OK;
  }
  return ERR;
}

bool Search::go(int r, int c, uint8_t v, bool f, int &wasfree) {
  wasfree = nwstng;
  while (proceed(r, c, v, f, true)) {
    if (backup()) return ERR;
    r = st[nwstng].r;
    c = st[nwstng].c;
    v = !st[nwstng].val;
    f = 0;
    wasfree = nwstng;
  }
  return OK;
}

/************************************************************************/
/* Advancing the pattern                                                */
/************************************************************************/

void Search::listneighbors(int g) {
  if (++stampv == 0) {
    std::fill(stamp.begin(), stamp.end(), 0);
    stampv = 1;
  }
  // dr2.c appends each changed cell and its neighbours (in this order),
  // skipping duplicates with a linear scan; a per-cell stamp does the same.
  static const int ORDER[9][2] = {{0, 0}, {-1, -1}, {-1, 0}, {-1, 1}, {0, -1},
                                  {0, 1}, {1, -1}, {1, 0}, {1, 1}};
  int lo = nays[g];
  ensure(lo + 9 * (nays[g] - chgd[g]) + (int)ulist.size() + 1);
  sortkeys.resize(9 * (nays[g] - chgd[g]) + ulist.size() + 1);
  const uint8_t *key = rule->sortkey;
  int w = lo;
  auto append = [&](int r, int c) {
    int i = idx(r, c);
    if (stamp[i] == stampv) return;
    stamp[i] = stampv;
    sortkeys[w - lo] = key[code[i]];
    chglist[w++] = {r, c};
  };
  for (int q = chgd[g]; q < nays[g]; q++) {
    int r = chglist[q].r, c = chglist[q].c;
    for (int k = 0; k < 9; k++) append(r + ORDER[k][0], c + ORDER[k][1]);
  }
  for (const Pt &u : ulist) append(u.r, u.c);
  chgd[g + 1] = w;

  // Sort into increasing order by number of UNK neighbours. dr2.c uses an
  // insertion sort; any stable sort gives the same order.
  int n = w - lo;
  if (n < 16) {
    for (int p = 1; p < n; p++) {
      Pt tmp = chglist[lo + p];
      uint8_t k = sortkeys[p];
      int q = p - 1;
      for (; q >= 0 && sortkeys[q] > k; q--) {
        chglist[lo + q + 1] = chglist[lo + q];
        sortkeys[q + 1] = sortkeys[q];
      }
      chglist[lo + q + 1] = tmp;
      sortkeys[q + 1] = k;
    }
  } else {
    int count[257] = {0};
    for (int p = 0; p < n; p++) count[sortkeys[p] + 1]++;
    for (int k = 1; k < 257; k++) count[k] += count[k - 1];
    sorted.resize(n);
    for (int p = 0; p < n; p++) sorted[count[sortkeys[p]]++] = chglist[lo + p];
    std::copy(sorted.begin(), sorted.end(), chglist.begin() + lo);
  }
}

void Search::changecurr(std::vector<uint8_t> &a, int g) {
  for (int q = chgd[g]; q < nays[g]; q++) {
    int i = idx(chglist[q].r, chglist[q].c);
    if (&a == &curr && a[i] == UNK)
      throw std::runtime_error(fmt("internal error in changecurr: r=%d c=%d",
                                   chglist[q].r, chglist[q].c));
    a[i] ^= 1;
  }
}

inline __attribute__((always_inline)) uint8_t Search::nxgen(int r, int c) const {
  int i = idx(r, c);
  if (curr[i] == UNK) return UNK;
  const uint8_t *a = &curr[i - S], *m = &curr[i], *b = &curr[i + S];
  int x = a[-1] + 3 * a[0] + 9 * a[1] + 27 * m[-1] + 81 * m[0] + 243 * m[1] +
          729 * b[-1] + 2187 * b[0] + 6561 * b[1];
  return rule->next3[x];
}

void Search::findchgcount(int g) {
  if (g < P.var[106])
    chgcount[g] = width[g] = height[g] = 0;
  else {
    chgcount[g] = 0;
    int maxc = -1, maxr = -1, minr = HT, minc = WD;
    for (int q = chgd[g]; q < nays[g]; q++) {
      int r = chglist[q].r, c = chglist[q].c;
      if (!(flag[idx(r, c)] & DONTCOUNT) && !(flag[idx(r, c)] & DONTCHECK)) {
        chgcount[g]++;
        minr = std::min(minr, r);
        maxr = std::max(maxr, r);
        minc = std::min(minc, c);
        maxc = std::max(maxc, c);
      }
    }
    width[g] = maxc == -1 ? 0 : maxc - minc + 1;
    height[g] = maxr == -1 ? 0 : maxr - minr + 1;
  }
  if (P.var[129] && g == 0) agesm[0] = nays[0] - chgd[0];
}

static inline int diff(int a, int b) { return a < b ? b - a : a - b; }

bool Search::trycell() {
  const long *var = P.var;
  int r = chglist[nay].r, c = chglist[nay].c;
  uint8_t val;

  while ((val = nxgen(r, c)) == UNK) {
    int ru = r, cu = c;
    if (bkgd[idx(r, c)] == UNK)               { ru = r;     cu = c;     }
    else if (bkgd[idx(r - 1, c)] == UNK)      { ru = r - 1; cu = c;     }
    else if (bkgd[idx(r, c - 1)] == UNK)      { ru = r;     cu = c - 1; }
    else if (bkgd[idx(r + 1, c)] == UNK)      { ru = r + 1; cu = c;     }
    else if (bkgd[idx(r, c + 1)] == UNK)      { ru = r;     cu = c + 1; }
    else if (bkgd[idx(r - 1, c - 1)] == UNK)  { ru = r - 1; cu = c - 1; }
    else if (bkgd[idx(r + 1, c - 1)] == UNK)  { ru = r + 1; cu = c - 1; }
    else if (bkgd[idx(r - 1, c + 1)] == UNK)  { ru = r - 1; cu = c + 1; }
    else if (bkgd[idx(r + 1, c + 1)] == UNK)  { ru = r + 1; cu = c + 1; }

    st[nwstng].gen = gen;
    st[nwstng].nay = nay;
    st[nwstng].chg = chg;

    bool f;
    if (replayPos < prefix.size()) { val = prefix[replayPos++]; f = false; }
    else { val = myrandom(100) < P.prob; f = true; }
    if (proceed(ru, cu, val, f, true)) return ERR;
  }

  if (val == bkgd[idx(r, c)]) return OK;

  // The cell is changed in the next generation; test whether that's allowed.
  if (r < 0 || r >= HT || c < 0 || c >= WD) return ERR;   // dr2.c: undefined
  ensure(chg);
  chglist[chg++] = {r, c};

  if (gen < var[106]) return OK;
  int fl = flag[idx(r, c)];
  if (fl & DONTCHANGE) return ERR;
  if (fl & DONTCOUNT) return OK;

  bool recentbig = true, recentwide = true, recenttall = true;
  if (var[100])
    for (int g = gen - 1; g >= 0 && g > gen - var[100]; g--)
      if (chgcount[g] <= P.maxchng) { recentbig = false; break; }
  if (var[125])
    for (int g = gen - 1; g >= 0 && g > gen - var[125]; g--)
      if (height[g] <= P.maxheight) { recenttall = false; break; }
  if (var[126])
    for (int g = gen - 1; g >= 0 && g > gen - var[126]; g--)
      if (width[g] <= P.maxwidth) { recentwide = false; break; }

  int minqr = HT, minqc = WD, maxqr = 0, maxqc = 0;
  for (int q = chgd[gen]; q < chg; q++) {
    int qr = chglist[q].r, qc = chglist[q].c;
    if (flag[idx(qr, qc)] & DONTCOUNT) continue;
    minqr = std::min(minqr, qr);
    maxqr = std::max(maxqr, qr);
    minqc = std::min(minqc, qc);
    maxqc = std::max(maxqc, qc);
  }
  int numcc = (int)P.reqchgcount.size();

  if (var[112]) {
    for (int q = chgd[gen]; q < chg - 1; q++) {
      int qr = chglist[q].r;
      if (qr >= minqr + P.maxheight && qr <= maxqr - P.maxheight) return ERR;
    }
  } else if (maxqr - minqr >= P.maxheight && recenttall && gen >= numcc)
    return ERR;

  if (var[113]) {
    for (int q = chgd[gen]; q < chg - 1; q++) {
      int qc = chglist[q].c;
      if (qc >= minqc + P.maxwidth && qc <= maxqc - P.maxwidth) return ERR;
    }
  } else if (maxqc - minqc >= P.maxwidth && recentwide && gen >= numcc)
    return ERR;

  int changecount = 1;
  for (int q = chgd[gen]; q < chg - 1; q++) {
    int qr = chglist[q].r, qc = chglist[q].c;
    if (flag[idx(qr, qc)] & DONTCOUNT) continue;
    if (++changecount > P.maxchng && recentbig && gen >= numcc) return ERR;
    if ((var[102] && diff(r - c, qr - qc) >= var[102]) ||
        (var[103] && diff(r + c, qr + qc) >= var[103]))
      return ERR;
  }

  if (var[107])
    for (int g = gen - var[107]; g >= gen - var[108] && g >= 0; g--)
      for (int q = chgd[g]; q < nays[g]; q++)
        if (chglist[q].r == r && chglist[q].c == c) return ERR;

  auto newcount = [&](int g0, long bound) {
    int cnt = 0;
    for (int q = chgd[gen]; q < chg; q++) {
      bool old = false;
      for (int m = chgd[g0]; m < nays[g0]; m++)
        if (chglist[m].r == chglist[q].r && chglist[m].c == chglist[q].c) { old = true; break; }
      if (!old) cnt++;
      if (cnt > bound) return true;
    }
    return false;
  };
  if (var[101] && gen > 0 && newcount(gen - 1, var[101])) return ERR;
  if (var[117] && gen >= var[118] && newcount(gen - (int)var[118], var[117])) return ERR;

  if (var[129]) {
    int g;
    for (g = 0; g < gen; g++) {
      bool hit = false;
      for (int m = chgd[g]; m < nays[g]; m++)
        if (chglist[m].r == r && chglist[m].c == c) { hit = true; break; }
      if (hit) break;
    }
    agesm[gen] += gen - g + 1;
    if (agesm[gen] > var[129]) return ERR;
  }

  if (var[137]) {
    int agesum = 0;
    for (int q = chgd[gen]; q < chg; q++) {
      int qr = chglist[q].r, qc = chglist[q].c;
      int pgen = gen;
      for (int g = gen - 1; g >= 0 && g >= pgen - var[138] - 1; g--)
        for (int m = chgd[g]; m < nays[g]; m++)
          if (chglist[m].r == qr && chglist[m].c == qc) { pgen = g; break; }
      agesum += gen - pgen + 1;
      if (agesum > var[137]) return ERR;
    }
  }

  if (var[104] && 3 * c < 2 * gen + var[104]) return ERR;   // right at >= 2c/3
  if (var[105] && 3 * r < 2 * gen + var[105]) return ERR;   // down at >= 2c/3
  if (var[109] && 2 * r < gen + var[109]) return ERR;       // down at >= c/2
  return OK;
}

bool Search::computecellorbackup() {
  if (++countlo == 1000000) { countlo = 0; counthi++; }
  steps++;

  if (!found && !(P.var[139] && (chgd[gen] - nays[gen - 1]) > P.var[139]) && trycell() == OK) {
    nay++;
    return OK;
  }

  changecurr(curr, gen - 1);   // curr <- bkgd
  found = false;
  if (backup()) return ERR;
  int wasfree;
  if (go(st[nwstng].r, st[nwstng].c, !st[nwstng].val, 0, wasfree)) return ERR;

  gen = st[wasfree].gen;
  nay = st[wasfree].nay;
  chg = st[wasfree].chg;
  changecurr(curr, gen - 1);

  if (P.var[129]) {   // recompute agesm[gen]
    agesm[gen] = 0;
    for (int q = chgd[gen]; q < chg; q++) {
      int g;
      for (g = 0; g < gen; g++) {
        bool hit = false;
        for (int m = chgd[g]; m < nays[g]; m++)
          if (chglist[m].r == chglist[q].r && chglist[m].c == chglist[q].c) { hit = true; break; }
        if (hit) break;
      }
      agesm[gen] += gen - g + 1;
    }
  }
  return OK;
}

/************************************************************************/
/* Main loop                                                            */
/************************************************************************/

void Search::start() {
  if ((P.symm == DIAGSYMM || P.symm == ROT90SYMM || P.symm == XSYMM || P.symm == FULLSYMM) &&
      HT != WD)
    throw std::runtime_error("this symmetry requires height = width");
  nwstng = 0;           // make initialization un-backup-able
  changecurr(curr, 0);  // curr <- gen 0
  found = false;
  listneighbors(0);
  nay = nays[0];
  chg = chgd[gen = 1];
  findchgcount(0);
}

int Search::period() const {
  int numchgs = nays[gen] - chgd[gen];
  for (int g = gen - 1; g >= 0; g--) {
    if (nays[g] - chgd[g] != numchgs) continue;
    int q;
    for (q = chgd[g]; q < nays[g]; q++) {
      int i = idx(chglist[q].r, chglist[q].c);
      if (curr[i] == bkgd[i]) break;
    }
    if (q == nays[g]) return gen - g;
  }
  return 0;
}

bool Search::semifizzle() const {
  for (int q = chgd[gen]; q < nays[gen]; q++)
    if (!(flag[idx(chglist[q].r, chglist[q].c)] & DONTCOUNT)) return false;
  return true;
}

uint64_t Search::hash() const {
  uint64_t h = 0;
  for (int g = 0; g <= gen; g++)
    for (int q = chgd[g]; q < nays[g]; q++)
      h = 31 * (31 * h + (uint64_t)(int64_t)chglist[q].r) + (uint64_t)(int64_t)chglist[q].c;
  return h;
}

bool Search::run(Sink &sink) {
  const long *var = P.var;
  int numcc = (int)P.reqchgcount.size();
  unsigned iter = 0;

  while (computecellorbackup() == OK) {
    if (countlo == 0 && (counthi < 50 || counthi % 10 == 0)) sink.tick(*this);
    if (!found && (++iter & 1023) == 0 && sink.poll(*this)) return false;

    if (nay != chgd[gen]) continue;   // not done with this gen yet

    if (gen > maxgenreached) {
      maxgenreached = gen;
      sink.newMaxGen(*this);
    }
    nays[gen] = chg;
    findchgcount(gen);
    changecurr(curr, gen - 1);
    changecurr(curr, gen);

    auto reject = [&]() { found = true; gen++; };

    if (var[110] && gen >= var[110]) {
      bool toomanytwos = true;
      for (int g = gen - var[110]; g <= gen; g++)
        if (chgcount[g] != 2) { toomanytwos = false; break; }
      if (toomanytwos) { sink.note(*this, "Too many 2s\n"); reject(); continue; }
    }
    if (var[121] && gen == var[121] && chgcount[gen] == var[122]) {
      sink.note(*this, fmt("chgcount[%d] can't be %ld\n", gen, var[122]));
      reject();
      continue;
    }
    if (var[123]) {
      if (gen < var[123] && chgcount[gen] != var[124]) { reject(); continue; }
      if (gen == var[123] && chgcount[gen] == var[124]) {
        sink.note(*this, fmt("chgcount[%d] can't be %ld\n", gen, var[124]));
        reject();
        continue;
      }
    }
    if (gen < numcc &&
        ((P.reqchgcount[gen] >= 0 && nays[gen] - chgd[gen] != P.reqchgcount[gen]) ||
         (P.reqchgcount[gen] < 0 && nays[gen] - chgd[gen] == -P.reqchgcount[gen]))) {
      reject();
      continue;
    }
    if (var[128] && gen >= var[128]) {
      int g2 = gen - (int)var[128];
      if (!(chgcount[gen] == chgcount[g2] &&
            ((width[gen] == width[g2] && height[gen] == height[g2]) ||
             (width[gen] == height[g2] && height[gen] == width[g2])))) {
        reject();
        continue;
      }
    }
    if (var[116] && gen >= 18) {
      static const int pat[19] = {1, 3, 3, 5, 6, 4, 4, 4, 3, 1, 3, 3, 5, 6, 4, 4, 4, 3, 1};
      bool match = true;
      for (int k = 0; k < 19; k++)
        if (chgcount[gen - k] != pat[k]) { match = false; break; }
      if (match) { sink.note(*this, "5c/9 continues too long\n"); reject(); continue; }
    }
    if (var[111] && gen >= var[111]) {
      bool ok = true;
      int g2 = gen - (int)var[111];
      for (int q = chgd[g2]; q < nays[g2]; q++) {
        int rr = chglist[q].r, cc = chglist[q].c, i = idx(rr, cc);
        if (rr >= var[132] && cc >= var[133] && rr <= var[134] && cc <= var[135] &&
            bkgd[i] == curr[i]) { ok = false; break; }
      }
      if (!ok) { reject(); continue; }
    }
    if (var[120] && chgcount[gen] && chgcount[gen] < var[120]) { reject(); continue; }

    uint64_t h = hash();
    int per;
    if (nays[gen] == chgd[gen]) {
      found = true;
      // With DONTCHECK cells the background there may not be stable, so an
      // empty change list may really be an oscillation (dr2.c's logic).
      bool actuallyperiodic = false;
      for (const Pt &u : ulist)
        if (rule->cons3[code[idx(u.r, u.c)]] & CONS_BAD) { actuallyperiodic = true; break; }
      if (actuallyperiodic) {
        per = gen;
        if (per > 1) sink.outcome(*this, PERIODIC, per, semifzl, h);
        else if (semifzl) sink.outcome(*this, STABLE, per, semifzl, h);
      } else if (sink.hashnew(h))
        sink.outcome(*this, FIZZLE, 0, false, h);
    } else if ((per = period())) {
      found = true;
      semifzl = semifizzle();
      if (sink.hashnew(h)) {
        if (per > 1) sink.outcome(*this, PERIODIC, per, semifzl, h);
        else if (semifzl) sink.outcome(*this, STABLE, per, semifzl, h);
      }
    } else if (gen == P.maxgen) {
      found = true;
      if (sink.hashnew(h)) sink.outcome(*this, MAXGEN, 0, false, h);
    } else {
      listneighbors(gen);
      nay = nays[gen];
      chg = chgd[gen + 1];
    }
    gen++;
    if (var[129]) agesm[gen] = 0;
  }
  return true;
}

/************************************************************************/
/* Work splitting                                                       */
/************************************************************************/

bool Search::donate(std::vector<uint8_t> &path, double &w) {
  path.clear();
  int j = 0;
  for (int i = 0; i < nwstng; i++) {
    Setting &s = st[i];
    if (!s.decision) continue;
    if (s.free) {
      path.push_back(!s.val);
      s.free = false;
      s.donated = true;
      w = std::ldexp(weight, -(j - (int)prefix.size() + 1));
      donatedWeight += w;
      return true;
    }
    path.push_back(s.val);
    j++;
  }
  return false;
}

void Search::pending(std::vector<std::pair<std::vector<uint8_t>, double>> &out) const {
  std::vector<uint8_t> path;
  int j = 0;
  for (int i = 0; i < nwstng; i++) {
    const Setting &s = st[i];
    if (!s.decision) continue;
    if (s.free) {
      std::vector<uint8_t> alt = path;
      alt.push_back(!s.val);
      out.push_back({alt, std::ldexp(weight, -(j - (int)prefix.size() + 1))});
    }
    path.push_back(s.val);
    j++;
  }
  out.push_back({path, std::ldexp(weight, -(j - (int)prefix.size()))});
}

double Search::progress() const {
  double done = 0;
  int j = 0;
  for (int i = 0; i < nwstng; i++) {
    const Setting &s = st[i];
    if (!s.decision) continue;
    if (j >= (int)prefix.size() && !s.free && !s.donated)
      done += std::ldexp(weight, -(j - (int)prefix.size() + 1));
    j++;
  }
  return done;
}

/************************************************************************/
/* Reporting (text identical to dr2.c)                                  */
/************************************************************************/

std::string Search::dispchgcts(int g) const {
  std::string s;
  bool different = false;
  for (int i = 0; i <= g; i++)
    if (nays[i] - chgd[i] != chgcount[i]) different = true;
  if (different) {
    s += "Full change counts:";
    for (int i = 0; i <= g; i++) {
      if (i && i % 5 == 0) s += " ";
      s += fmt(" %d", nays[i] - chgd[i]);
    }
    s += "\n";
  }
  s += "Change counts:";
  for (int i = 0; i <= g; i++) {
    if (i && i % 5 == 0) s += " ";
    s += fmt(" %d", chgcount[i]);
  }
  s += "\nSizes:";
  for (int i = 0; i <= g; i++) {
    if (i && i % 5 == 0) s += " ";
    s += fmt(" %dx%d", height[i], width[i]);
  }
  s += "\n";
  if (P.var[129]) {
    s += "Age sums:";
    for (int i = 0; i <= g; i++) {
      if (i && i % 5 == 0) s += " ";
      s += fmt(" %d", agesm[i]);
    }
    s += "\n";
  }
  return s;
}

std::string Search::display(int g) const {
  int minr = HT, maxr = -1, minc = WD, maxc = -1;
  for (int r = 2; r < HT - 2; r++)
    for (int c = 2; c < WD - 2; c++)
      if (bkgd[idx(r, c)] == ON) {
        minr = std::min(minr, r); maxr = std::max(maxr, r);
        minc = std::min(minc, c); maxc = std::max(maxc, c);
      }
  for (int q = chgd[g]; q < nays[g]; q++) {
    minr = std::min(minr, chglist[q].r); maxr = std::max(maxr, chglist[q].r);
    minc = std::min(minc, chglist[q].c); maxc = std::max(maxc, chglist[q].c);
  }
  if (maxr < 0) { minr = maxr = HT / 2; minc = maxc = WD / 2; }
  minr -= 2; maxr += 2; minc -= 2; maxc += 2;
  std::string s = fmt("Gen %d.  Rows %d - %d.  Cols %d - %d.\n", g, minr, maxr, minc, maxc);
  for (int r = minr; r <= maxr; r++) {
    int lastc;
    for (lastc = maxc; lastc > minc; lastc--)
      if (bkgd[idx(r, lastc)] != UNK) break;
    bool changed = false;
    for (int c = minc; c <= lastc; c++) {
      uint8_t b = bkgd[idx(r, c)];
      if (b != UNK) {
        changed = false;
        for (int q = chgd[g]; q < nays[g]; q++)
          if (chglist[q].r == r && chglist[q].c == c) { changed = true; break; }
      }
      s += b == OFF ? (changed ? '1' : '.') : b == ON ? (changed ? '0' : 'o') : ',';
    }
    s += "\n";
  }
  return s;
}

enum { NWR, NER, SWR, SER, NWC, NEC, SWC, SEC };

void Search::getrotordesc(int period, int minr, int maxr, int minc, int maxc,
                          int orientation, std::string &out) const {
  int h = maxr - minr + 1, w = maxc - minc + 1;
  int r0 = 0, c0 = 0, dr0 = 0, dc0 = 0, dr1 = 0, dc1 = 0, lth = 1;
  switch (orientation) {
    case NWR: r0 = minr; c0 = minc; dr0 = 0;  dc0 = 1;  dr1 = 1;  dc1 = 0;  lth = w; break;
    case NWC: r0 = minr; c0 = minc; dr0 = 1;  dc0 = 0;  dr1 = 0;  dc1 = 1;  lth = h; break;
    case NER: r0 = minr; c0 = maxc; dr0 = 0;  dc0 = -1; dr1 = 1;  dc1 = 0;  lth = w; break;
    case NEC: r0 = minr; c0 = maxc; dr0 = 1;  dc0 = 0;  dr1 = 0;  dc1 = -1; lth = h; break;
    case SWR: r0 = maxr; c0 = minc; dr0 = 0;  dc0 = 1;  dr1 = -1; dc1 = 0;  lth = w; break;
    case SWC: r0 = maxr; c0 = minc; dr0 = -1; dc0 = 0;  dr1 = 0;  dc1 = 1;  lth = h; break;
    case SER: r0 = maxr; c0 = maxc; dr0 = 0;  dc0 = -1; dr1 = -1; dc1 = 0;  lth = w; break;
    case SEC: r0 = maxr; c0 = maxc; dr0 = -1; dc0 = 0;  dr1 = 0;  dc1 = -1; lth = h; break;
  }
  int maxcount = h * w + h + w - lth;
  int rotorsize = 0;
  for (int r = minr; r <= maxr; r++)
    for (int c = minc; c <= maxc; c++) rotorsize += cell[idx(r, c)] != STATOR;

  out = fmt("p%d r%d %dx%d ", period, rotorsize, h + w - lth, lth);
  if ((int)out.size() + maxcount > 1000) {   // dr2.c's MAXROTORDESCLTH
    out += " ROTOR DESCRIPTOR TOO LONG.";
    return;
  }
  int r = r0, c = c0;
  for (int count = 1; count < maxcount; r += dr0, c += dc0, count++) {
    if (count % (lth + 1) == 0) {
      r += dr1 - (lth + 1) * dr0;
      c += dc1 - (lth + 1) * dc0;
      out += ' ';
    } else {
      int i = idx(r, c);
      if (cell[i] == STATOR) out += '.';
      else {
        char ch = cell[i] ? '@' : '0';
        for (int k = 0; k < 9; k++)
          if (k != 4 && cell[i + OFFS[k]] == STATOR) {
            uint8_t v = curr[i + OFFS[k]];
            ch += v == ON ? 1 : v == UNK ? 16 : 0;   // dr2.c's UNK is 16
          }
        out += ch;
      }
    }
  }
}

void Search::fillcell(int mingen, int maxgen, int &minr, int &maxr, int &minc, int &maxc) {
  std::fill(cell.begin(), cell.end(), (uint8_t)STATOR);
  minr = HT; maxr = -1; minc = WD; maxc = -1;
  for (int g0 = mingen; g0 <= maxgen; g0++)
    for (int q0 = chgd[g0]; q0 < nays[g0]; q0++) {
      int r = chglist[q0].r, c = chglist[q0].c, count = 0;
      bool first = true;
      for (int g1 = mingen; g1 <= maxgen && first; g1++)
        for (int q1 = chgd[g1]; q1 < nays[g1]; q1++)
          if (chglist[q1].r == r && chglist[q1].c == c) {
            if (g1 < g0) { first = false; break; }
            count++;
          }
      if (!first) continue;
      if (count < maxgen - mingen + 1) {   // another rotor cell
        int i = idx(r, c);
        cell[i] = bkgd[i];
        for (int q1 = chgd[mingen]; q1 < nays[mingen]; q1++)
          if (chglist[q1].r == r && chglist[q1].c == c) cell[i] ^= 1;
        minr = std::min(minr, r); maxr = std::max(maxr, r);
        minc = std::min(minc, c); maxc = std::max(maxc, c);
      }
    }
}

OscInfo Search::oscinfo(int p, char prefixch) {
  OscInfo info;
  int minr, maxr, minc, maxc, minorient, maxorient;
  std::string rotordesc, mindesc;
  int knownIdx = -1;
  auto lookup = [&]() {
    knownIdx = -1;
    if (known) {
      auto it = known->index.find(mindesc);
      if (it != known->index.end()) knownIdx = it->second;
    }
  };
  auto orients = [&]() {
    if (maxc - minc > maxr - minr) { minorient = NWR; maxorient = SER; }
    else if (maxc - minc < maxr - minr) { minorient = NWC; maxorient = SEC; }
    else { minorient = NWR; maxorient = SEC; }
  };

  if (prefixch == 'p') {   // rotor of an oscillator
    fillcell(gen - p, gen - 1, minr, maxr, minc, maxc);
    orients();
    mindesc = "z";
    for (int g = gen; g > gen - p; g--) {
      for (int o = minorient; o <= maxorient; o++) {
        getrotordesc(p, minr, maxr, minc, maxc, o, rotordesc);
        if (rotordesc < mindesc) mindesc = rotordesc;
      }
      changecurr(cell, g);
      changecurr(cell, g - 1);
    }
    lookup();
  } else {   // 'rotor' of the whole history (fizzle, stable, eventually periodic)
    for (int g = 0; g <= (P.var[119] ? 0 : gen); g++) {
      int g0 = g == gen ? 0 : g;
      fillcell(g0, gen, minr, maxr, minc, maxc);
      orients();
      mindesc = "z";
      for (int o = minorient; o <= maxorient; o++) {
        getrotordesc(gen - g0, minr, maxr, minc, maxc, o, rotordesc);
        rotordesc[0] = prefixch;
        if (rotordesc < mindesc) mindesc = rotordesc;
      }
      lookup();
      if (knownIdx >= 0) break;
    }
  }

  // Is the rotor disconnected? If so, find the gap between its pieces.
  for (int c = minc; c <= maxc; c++)
    if (cell[idx(minr, c)] <= ON) { cell[idx(minr, c)] = CONN; break; }
  int dist;
  bool unconcount = true;
  for (dist = 1; dist < 100 && unconcount; dist++) {
    bool changesome;
    do {
      changesome = false;
      unconcount = false;
      for (int r = minr; r <= maxr; r++)
        for (int c = minc; c <= maxc; c++)
          if (cell[idx(r, c)] <= ON) {
            for (int rn = std::max(r - dist, minr); rn <= r + dist && rn <= maxr; rn++)
              for (int cn = std::max(c - dist, minc); cn <= c + dist && cn <= maxc; cn++)
                if (cell[idx(rn, cn)] == CONN) { cell[idx(r, c)] = CONN; changesome = true; }
            if (cell[idx(r, c)] <= ON) unconcount = true;
          }
    } while (changesome);
  }
  dist--;

  info.desc = mindesc;
  info.known = knownIdx >= 0;
  info.gap = dist > 1 ? dist - 1 : 0;
  if (info.known) info.name = known->names[knownIdx];
  info.line = mindesc + "\t";
  if (info.known)
    info.line += dist > 1 ? fmt("   %s (gap = %d)\n", info.name.c_str(), dist - 1)
                          : "   " + info.name + "\n";
  else if (dist > 1)
    info.line += fmt("<- unknown: split rotor (gap = %d)\n", dist - 1);
  else
    info.line += prefixch == 'u' ? "<- unknown\n" : "<- UNKNOWN\n";
  return info;
}

}  // namespace drift
