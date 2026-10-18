// Checks the rule tables:
//  1. For outer-totalistic rules, cons3 forces exactly what dr2.c's
//     consistable forces (iterated as dr2.c's consistify does), so the
//     search tree is identical to dr2.c's.
//  2. next3 and cons3 agree with direct simulation on fully known windows.
//  3. Rule strings round-trip (INT canonical form, MAP).
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>

#include "rule.h"

using namespace drift;

static int failures = 0;
#define CHECK(cond, ...)                         \
  do {                                           \
    if (!(cond)) {                               \
      if (failures++ < 20) printf(__VA_ARGS__);  \
    }                                            \
  } while (0)

static const int NBIT[9] = {0x80, 0x40, 0x20, 0x10, 0, 0x08, 0x04, 0x02, 0x01};

// dr2.c's initconsistable(), for a totalistic rule given as rule[2][9]
enum { NOINFO, INCONSIS, NAYSOFF, NAYSON, CELLOFF, CELLON };
static int drTable(const bool rule[2][9], int val, int oncount, int unkcount) {
  int survct = 0, deathct = 0, birthct = 0, sterilect = 0;
  if (val == ON || val == UNK)
    for (int i = oncount; i <= oncount + unkcount; i++)
      if (rule[1][i]) survct++; else deathct++;
  if (val == OFF || val == UNK)
    for (int i = oncount; i <= oncount + unkcount; i++)
      if (rule[0][i]) birthct++; else sterilect++;
  if (sterilect == 0 && survct == 0) return INCONSIS;
  if (val == UNK && sterilect == 0) return CELLON;
  if (val == UNK && survct == 0) return CELLOFF;
  if (unkcount == 0) return NOINFO;
  if (val == OFF) {
    if (sterilect == 1 && !rule[0][oncount]) return NAYSOFF;
    if (sterilect == 1 && !rule[0][oncount + unkcount]) return NAYSON;
    return NOINFO;
  }
  if (val == ON) {
    if (survct == 1 && rule[1][oncount]) return NAYSOFF;
    if (survct == 1 && rule[1][oncount + unkcount]) return NAYSON;
    return NOINFO;
  }
  if (sterilect == 1 && !rule[0][oncount] && survct == 1 && rule[1][oncount]) return NAYSOFF;
  if (sterilect == 1 && !rule[0][oncount + unkcount] && survct == 1 && rule[1][oncount + unkcount])
    return NAYSON;
  return NOINFO;
}

static void totalisticCheck(const Rule &R, const bool tot[2][9], const char *name) {
  for (int code = 0; code < NCODES; code++) {
    int v[9];
    for (int k = 0, x = code; k < 9; k++, x /= 3) v[k] = x % 3;
    // dr2.c: consistify(r,c) with goto START after forcing the cell
    bool bad = false;
    while (true) {
      int on = 0, unk = 0;
      for (int k = 0; k < 9; k++)
        if (k != 4) { on += v[k] == ON; unk += v[k] == UNK; }
      int t = drTable(tot, v[4], on, unk);
      if (t == INCONSIS) { bad = true; break; }
      if (t == CELLON) { v[4] = ON; continue; }
      if (t == CELLOFF) { v[4] = OFF; continue; }
      if (t == NAYSOFF || t == NAYSON)
        for (int k = 0; k < 9; k++)
          if (k != 4 && v[k] == UNK) v[k] = t == NAYSON ? ON : OFF;
      break;
    }
    uint32_t e = R.cons3[code];
    if (bad) {
      CHECK(e & CONS_BAD, "%s: code %d should be inconsistent\n", name, code);
      continue;
    }
    // The cells dr2.c leaves still form a window that may be inconsistent only
    // through the forced values; our table forces in one step.
    CHECK(!(e & CONS_BAD), "%s: code %d wrongly inconsistent\n", name, code);
    for (int k = 0, x = code; k < 9; k++, x /= 3) {
      int orig = x % 3;
      if (orig != UNK) continue;
      int mine = (e >> k) & 1 ? ON : (e >> (9 + k)) & 1 ? OFF : UNK;
      CHECK(mine == v[k], "%s: code %d position %d: dr2 %d, drift %d\n", name, code, k, v[k], mine);
    }
  }
}

int main() {
  std::mt19937 rng(12345);
  std::string err;

  // 1. Totalistic rules: Life, HighLife, Day & Night, and random ones.
  std::vector<std::string> rules = {"B3/S23", "B36/S23", "B3678/S34678", "B2/S", "B1357/S1357"};
  for (int i = 0; i < 40; i++) {
    std::string s = "B";
    for (int n = 1; n <= 8; n++) if (rng() & 1) s += char('0' + n);
    s += "/S";
    for (int n = 0; n <= 8; n++) if (rng() & 1) s += char('0' + n);
    rules.push_back(s);
  }
  for (const std::string &rs : rules) {
    Rule R;
    if (!R.parse(rs, err)) { printf("parse %s: %s\n", rs.c_str(), err.c_str()); failures++; continue; }
    bool tot[2][9] = {};
    for (int m = 0; m < 256; m++) {
      tot[0][__builtin_popcount(m)] = R.birth[m];
      tot[1][__builtin_popcount(m)] = R.survive[m];
    }
    CHECK(R.isTotalistic(), "%s not totalistic?\n", rs.c_str());
    totalisticCheck(R, tot, rs.c_str());
    // dr2.c's classic reading of the same rule without letters
    Rule C;
    std::string digits = rs.substr(1);
    size_t sl = digits.find("/S");
    digits = digits.substr(0, sl) + "/" + digits.substr(sl + 2);
    if (C.parse(digits, err, true))
      for (int m = 0; m < 256; m++)
        CHECK(C.birth[m] == R.birth[m] && C.survive[m] == R.survive[m],
              "classic parse of %s differs\n", digits.c_str());
  }

  // 2. Fully known windows against direct simulation, for INT and MAP rules.
  std::vector<std::string> intRules = {"B2-a/S12", "B2ei3aeikqr/S2-a3", "B3/S23",
                                       "B2n3/S23-q", "B34kz5e7c/S23-a4ityz5k"};
  for (int i = 0; i < 10; i++) {   // random MAP rules
    std::string m = "MAP";
    const char *b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    m += b64[rng() % 32];   // first bit is B0: keep it clear
    for (int k = 1; k < 86; k++) m += b64[rng() % 64];
    intRules.push_back(m);
  }
  for (const std::string &rs : intRules) {
    Rule R;
    if (!R.parse(rs, err)) { printf("parse %s: %s\n", rs.c_str(), err.c_str()); failures++; continue; }
    for (int w = 0; w < 512; w++) {
      int code = 0, mask = 0;
      for (int k = 0; k < 9; k++) {
        int bit = (w >> k) & 1;
        code += bit * POW3[k];
        if (k != 4 && bit) mask |= NBIT[k];
      }
      bool centre = (w >> 4) & 1;
      bool nxt = centre ? R.survive[mask] : R.birth[mask];
      CHECK(R.next3[code] == (nxt ? ON : OFF), "%s: next3 wrong for window %03x\n", rs.c_str(), w);
      CHECK(((R.cons3[code] & CONS_BAD) != 0) == (nxt != centre),
            "%s: cons3 wrong for window %03x\n", rs.c_str(), w);
    }
    // Round trip through the canonical string
    Rule R2;
    if (!R2.parse(R.canonical(), err)) { printf("reparse %s: %s\n", R.canonical().c_str(), err.c_str()); failures++; continue; }
    for (int m = 0; m < 256; m++)
      CHECK(R.birth[m] == R2.birth[m] && R.survive[m] == R2.survive[m],
            "%s: canonical %s doesn't round-trip\n", rs.c_str(), R.canonical().c_str());
  }

  // 3. Known values
  Rule L;
  L.parse("B3/S23", err);
  CHECK(L.canonical() == "B3/S23", "Life canonical is %s\n", L.canonical().c_str());
  Rule J;
  J.parse("B2-a/S12", err);
  CHECK(J.birth[0x18] && !J.birth[0x03] && J.survive[0x80], "B2-a/S12 masks wrong\n");
  CHECK(!J.invariantUnder(NOSYMM) == false, "symmetry check\n");
  Rule G;
  CHECK(G.parse("23/3", err) && G.canonical() == "B3/S23", "Golly 23/3 reading\n");
  CHECK(G.parse("3/23", err, true) && G.canonical() == "B3/S23", "dr2 3/23 reading\n");
  CHECK(!G.parse("B03/S23", err), "B0 should be rejected\n");

  if (failures) printf("%d FAILURES\n", failures);
  else printf("rule tests passed (%zu totalistic, %zu INT/MAP rules)\n", rules.size(), intRules.size());
  return failures != 0;
}
