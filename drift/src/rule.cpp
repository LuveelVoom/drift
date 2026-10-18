#include "rule.h"

#include <cctype>
#include <vector>

namespace drift {

const int POW3[9] = {1, 3, 9, 27, 81, 243, 729, 2187, 6561};
const int DR[9] = {-1, -1, -1, 0, 0, 0, 1, 1, 1};
const int DC[9] = {-1, 0, 1, -1, 0, 1, -1, 0, 1};

// Hensel neighbourhood bit of each window position (centre has none):
// NW=0x80 N=0x40 NE=0x20 W=0x10 E=0x08 SW=0x04 S=0x02 SE=0x01
static const int NBIT[9] = {0x80, 0x40, 0x20, 0x10, 0, 0x08, 0x04, 0x02, 0x01};

// Hensel isotropic neighbourhood classes (from catforce-int/CatForce/LifeAPI.h,
// which takes them from the ca-rules crate, following Golly).
static const struct { char n; char l; uint8_t masks[8]; int cnt; } HENSEL[] = {
  {'0','c',{0x00},1},
  {'1','c',{0x01,0x04,0x20,0x80},4},
  {'1','e',{0x02,0x08,0x10,0x40},4},
  {'2','c',{0x05,0x21,0x84,0xa0},4},
  {'2','e',{0x0a,0x12,0x48,0x50},4},
  {'2','k',{0x0c,0x11,0x22,0x30,0x41,0x44,0x82,0x88},8},
  {'2','a',{0x03,0x06,0x09,0x14,0x28,0x60,0x90,0xc0},8},
  {'2','i',{0x18,0x42},2},
  {'2','n',{0x24,0x81},2},
  {'3','c',{0x25,0x85,0xa1,0xa4},4},
  {'3','e',{0x1a,0x4a,0x52,0x58},4},
  {'3','k',{0x32,0x4c,0x51,0x8a},4},
  {'3','a',{0x0b,0x16,0x68,0xd0},4},
  {'3','i',{0x07,0x29,0x94,0xe0},4},
  {'3','n',{0x0d,0x15,0x23,0x61,0x86,0xa8,0xb0,0xc4},8},
  {'3','y',{0x31,0x45,0x8c,0xa2},4},
  {'3','q',{0x26,0x2c,0x34,0x64,0x83,0x89,0x91,0xc1},8},
  {'3','j',{0x0e,0x13,0x2a,0x49,0x54,0x70,0x92,0xc8},8},
  {'3','r',{0x19,0x1c,0x38,0x43,0x46,0x62,0x98,0xc2},8},
  {'4','c',{0xa5},1},
  {'4','e',{0x5a},1},
  {'4','k',{0x33,0x4d,0x55,0x71,0x8e,0xaa,0xb2,0xcc},8},
  {'4','a',{0x0f,0x17,0x2b,0x69,0x96,0xd4,0xe8,0xf0},8},
  {'4','i',{0x1d,0x63,0xb8,0xc6},4},
  {'4','n',{0x27,0x2d,0x87,0x95,0xa9,0xb4,0xe1,0xe4},8},
  {'4','y',{0x35,0x65,0x8d,0xa3,0xa6,0xac,0xb1,0xc5},8},
  {'4','q',{0x36,0x6c,0x8b,0xd1},4},
  {'4','j',{0x3a,0x4e,0x53,0x59,0x5c,0x72,0x9a,0xca},8},
  {'4','r',{0x1b,0x1e,0x4b,0x56,0x6a,0x78,0xd2,0xd8},8},
  {'4','t',{0x39,0x47,0x9c,0xe2},4},
  {'4','w',{0x2e,0x74,0x93,0xc9},4},
  {'4','z',{0x3c,0x66,0x99,0xc3},4},
  {'5','c',{0x5b,0x5e,0x7a,0xda},4},
  {'5','e',{0xa7,0xad,0xb5,0xe5},4},
  {'5','k',{0x75,0xae,0xb3,0xcd},4},
  {'5','a',{0x2f,0x97,0xe9,0xf4},4},
  {'5','i',{0x1f,0x6b,0xd6,0xf8},4},
  {'5','n',{0x3b,0x4f,0x57,0x79,0x9e,0xdc,0xea,0xf2},8},
  {'5','y',{0x5d,0x73,0xba,0xce},4},
  {'5','q',{0x3e,0x6e,0x76,0x7c,0x9b,0xcb,0xd3,0xd9},8},
  {'5','j',{0x37,0x6d,0x8f,0xab,0xb6,0xd5,0xec,0xf1},8},
  {'5','r',{0x3d,0x67,0x9d,0xb9,0xbc,0xc7,0xe3,0xe6},8},
  {'6','c',{0x5f,0x7b,0xde,0xfa},4},
  {'6','e',{0xaf,0xb7,0xed,0xf5},4},
  {'6','k',{0x77,0x7d,0xbb,0xbe,0xcf,0xdd,0xee,0xf3},8},
  {'6','a',{0x3f,0x6f,0x9f,0xd7,0xeb,0xf6,0xf9,0xfc},8},
  {'6','i',{0xbd,0xe7},2},
  {'6','n',{0x7e,0xdb},2},
  {'7','c',{0x7f,0xdf,0xfb,0xfe},4},
  {'7','e',{0xbf,0xef,0xf7,0xfd},4},
  {'8','c',{0xff},1},
};
static const int NHENSEL = sizeof(HENSEL) / sizeof(HENSEL[0]);

static bool parseHensel(std::string r, bool *birth, bool *survive,
                        std::string &err, bool classicDefault) {
  bool hasBS = false;
  for (char ch : r)
    if (ch == 'B' || ch == 'b' || ch == 'S' || ch == 's') hasBS = true;
  if (!hasBS) {
    size_t slash = r.find('/');
    if (classicDefault)                    // dr2.c: birth first, '/' toggles
      r = "B" + (slash == std::string::npos ? r : r.substr(0, slash) + "/S" + r.substr(slash + 1));
    else if (slash == std::string::npos) {
      err = "expected something like B3/S23";
      return false;
    } else                                 // Golly: survival/birth
      r = "S" + r.substr(0, slash) + "/B" + r.substr(slash + 1);
  }

  int mode = classicDefault ? 0 : -1;   // 0 = birth, 1 = survival
  size_t i = 0;
  while (i < r.size()) {
    char ch = r[i];
    if (ch == '/') { if (classicDefault && mode >= 0) mode = 1 - mode; i++; continue; }
    if (ch == 'B' || ch == 'b') { mode = 0; i++; continue; }
    if (ch == 'S' || ch == 's') { mode = 1; i++; continue; }
    if (mode < 0 || ch < '0' || ch > '8') {
      err = std::string("unexpected character '") + ch + "' in rule";
      return false;
    }
    i++;
    bool negate = false;
    if (i < r.size() && r[i] == '-') { negate = true; i++; }
    std::string letters;
    while (i < r.size() && isalpha((unsigned char)r[i]) && r[i] != 'B' &&
           r[i] != 'b' && r[i] != 'S' && r[i] != 's')
      letters += (char)tolower((unsigned char)r[i++]);
    for (char l : letters) {
      bool ok = false;
      for (int c = 0; c < NHENSEL; c++)
        if (HENSEL[c].n == ch && HENSEL[c].l == l) ok = true;
      if (!ok) {
        err = std::string("letter '") + l + "' is not valid after " + ch;
        return false;
      }
    }
    if (negate && letters.empty()) {
      err = std::string("'-' after ") + ch + " must be followed by letters";
      return false;
    }
    bool *dest = mode == 0 ? birth : survive;
    for (int c = 0; c < NHENSEL; c++) {
      if (HENSEL[c].n != ch) continue;
      bool listed = letters.find(HENSEL[c].l) != std::string::npos;
      bool on = letters.empty() ? true : negate ? !listed : listed;
      if (on)
        for (int m = 0; m < HENSEL[c].cnt; m++) dest[HENSEL[c].masks[m]] = true;
    }
  }
  return true;
}

static int base64Val(char c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  return -1;
}
static const char *B64 =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

// Golly MAP: 512 bits, bit index 256*NW+128*N+64*NE+32*W+16*C+8*E+4*SW+2*S+SE
static bool parseMap(const std::string &rule, bool *birth, bool *survive,
                     std::string &err) {
  std::string r = rule.substr(3);
  while (!r.empty() && r.back() == '=') r.pop_back();
  std::vector<int> bits;
  for (char ch : r) {
    int v = base64Val(ch);
    if (v < 0) { err = "invalid base64 character in MAP rule"; return false; }
    for (int k = 5; k >= 0; k--) bits.push_back((v >> k) & 1);
  }
  if (bits.size() < 512) { err = "MAP rule too short (need 86 base64 characters)"; return false; }
  for (int k = 0; k < 512; k++) {
    if (!bits[k]) continue;
    int mask = ((k & 0x1e0) >> 1) | (k & 0x0f);
    (k & 0x10 ? survive : birth)[mask] = true;
  }
  return true;
}

bool Rule::parse(const std::string &in, std::string &err, bool classicDefault) {
  std::string r;
  for (char ch : in)
    if (!isspace((unsigned char)ch)) r += ch;
  if (r.empty()) { err = "empty rule"; return false; }
  for (int m = 0; m < 256; m++) birth[m] = survive[m] = false;
  bool ok = (r.size() > 3 && (r.compare(0, 3, "MAP") == 0 || r.compare(0, 3, "map") == 0))
                ? parseMap(r, birth, survive, err)
                : parseHensel(r, birth, survive, err, classicDefault);
  if (!ok) return false;
  if (birth[0]) { err = "rules with B0 are not supported"; return false; }
  text = r;
  build();
  return true;
}

void Rule::build() {
  for (int code = 0; code < NCODES; code++) {
    int v[9], unk[9], nu = 0;
    for (int k = 0, x = code; k < 9; k++, x /= 3) {
      v[k] = x % 3;
      if (v[k] == UNK) unk[nu++] = k;
    }
    int key = 0;
    for (int k = 0; k < 9; k++) key += v[k] == ON ? 1 : v[k] == UNK ? 16 : 0;
    sortkey[code] = (uint8_t)key;

    // Enumerate completions of the unknown cells.
    bool canOn = false, canOff = false;   // possible next states (centre known)
    bool anyStable = false;
    int allOn = 0x1ff, allOff = 0x1ff;    // positions ON/OFF in every stable completion
    for (int a = 0; a < (1 << nu); a++) {
      int w[9];
      for (int k = 0; k < 9; k++) w[k] = v[k];
      for (int j = 0; j < nu; j++) w[unk[j]] = (a >> j) & 1;
      int mask = 0;
      for (int k = 0; k < 9; k++)
        if (k != 4 && w[k]) mask |= NBIT[k];
      bool nxt = w[4] ? survive[mask] : birth[mask];
      if (nxt) canOn = true; else canOff = true;
      if ((int)nxt == w[4]) {
        anyStable = true;
        int on = 0;
        for (int k = 0; k < 9; k++) if (w[k]) on |= 1 << k;
        allOn &= on;
        allOff &= ~on & 0x1ff;
      }
    }
    if (v[4] == UNK) next3[code] = UNK;
    else next3[code] = canOn && canOff ? UNK : canOn ? ON : OFF;

    int umask = 0;
    for (int j = 0; j < nu; j++) umask |= 1 << unk[j];
    if (!anyStable) cons3[code] = CONS_BAD;
    else cons3[code] = (uint32_t)(allOn & umask) | ((uint32_t)(allOff & umask) << 9);
  }
}

bool Rule::isTotalistic() const {
  for (int m = 0; m < 256; m++)
    for (int m2 = 0; m2 < 256; m2++)
      if (__builtin_popcount(m) == __builtin_popcount(m2) &&
          (birth[m] != birth[m2] || survive[m] != survive[m2]))
        return false;
  return true;
}

// Map a Hensel mask through a transformation of the (dr,dc) offsets.
static int transformMask(int mask, int t) {
  int out = 0;
  for (int k = 0; k < 9; k++) {
    if (k == 4 || !(mask & NBIT[k])) continue;
    int r = DR[k], c = DC[k], r2, c2;
    switch (t) {
      case 0: r2 = -r; c2 = c; break;    // flip rows
      case 1: r2 = r; c2 = -c; break;    // flip columns
      case 2: r2 = c; c2 = r; break;     // transpose
      case 3: r2 = c; c2 = -r; break;    // rotate 90
      case 4: r2 = -r; c2 = -c; break;   // rotate 180
      default: r2 = -c; c2 = -r; break;  // anti-transpose
    }
    out |= NBIT[(r2 + 1) * 3 + (c2 + 1)];
  }
  return out;
}

bool Rule::invariantUnder(int symm) const {
  std::vector<int> ts;
  switch (symm) {
    case HORSYMM: ts = {0}; break;
    case VERTSYMM: ts = {1}; break;
    case DIAGSYMM: ts = {2}; break;
    case ROT90SYMM: ts = {3}; break;
    case ROT180SYMM: ts = {4}; break;
    case PLUSSYMM: ts = {0, 1}; break;
    case XSYMM: ts = {2, 5}; break;
    case FULLSYMM: ts = {0, 2}; break;
    default: return true;
  }
  for (int t : ts)
    for (int m = 0; m < 256; m++) {
      int m2 = transformMask(m, t);
      if (birth[m] != birth[m2] || survive[m] != survive[m2]) return false;
    }
  return true;
}

std::string Rule::mapString() const {
  std::string bits;
  for (int k = 0; k < 512; k++) {
    int mask = ((k & 0x1e0) >> 1) | (k & 0x0f);
    bits += ((k & 0x10) ? survive[mask] : birth[mask]) ? '1' : '0';
  }
  while (bits.size() % 6) bits += '0';
  std::string out = "MAP";
  for (size_t i = 0; i < bits.size(); i += 6) {
    int v = 0;
    for (int j = 0; j < 6; j++) v = 2 * v + (bits[i + j] - '0');
    out += B64[v];
  }
  return out;
}

std::string Rule::canonical() const {
  if (!invariantUnder(FULLSYMM)) return mapString();   // non-isotropic
  std::string out;
  for (int part = 0; part < 2; part++) {
    out += part == 0 ? "B" : "/S";
    const bool *arr = part == 0 ? birth : survive;
    for (int n = 0; n <= 8; n++) {
      std::string on, off;
      int total = 0, onCount = 0;
      for (int c = 0; c < NHENSEL; c++) {
        if (HENSEL[c].n != '0' + n) continue;
        total++;
        if (arr[HENSEL[c].masks[0]]) { onCount++; on += HENSEL[c].l; }
        else off += HENSEL[c].l;
      }
      if (onCount == 0) continue;
      out += (char)('0' + n);
      if (onCount == total) continue;
      out += on.size() <= off.size() ? on : "-" + off;
    }
  }
  return out;
}

}  // namespace drift
