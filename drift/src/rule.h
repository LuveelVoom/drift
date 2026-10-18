// Rule handling: parsing of B/S, Hensel INT and Golly MAP rule strings, and
// the 3x3-window lookup tables the search uses.
//
// A 3x3 window is encoded in base 3 (OFF=0, ON=1, UNK=2), position k having
// weight 3^k, positions numbered row-major from the NW corner:
//      0 1 2
//      3 4 5
//      6 7 8
// so there are 3^9 = 19683 window codes.
#pragma once
#include <cstdint>
#include <string>

namespace drift {

enum : uint8_t { OFF = 0, ON = 1, UNK = 2 };

constexpr int NCODES = 19683;
extern const int POW3[9];
extern const int DR[9], DC[9];       // row/col offset of window position k

// cons3[] entry: 0 = nothing forced, CONS_BAD = no stable completion exists,
// otherwise bit k (k<9) = position k forced ON, bit 9+k = forced OFF.
constexpr uint32_t CONS_BAD = 1u << 31;

enum Symm { NOSYMM, HORSYMM, DIAGSYMM, ROT90SYMM, ROT180SYMM, PLUSSYMM,
            XSYMM, FULLSYMM, VERTSYMM };

struct Rule {
  bool birth[256] = {}, survive[256] = {};   // indexed by Hensel mask
  std::string text;                          // as given by the user

  uint8_t next3[NCODES];    // next state of centre: OFF, ON or UNK
  uint32_t cons3[NCODES];   // still-life consistency (see CONS_BAD)
  uint8_t sortkey[NCODES];  // dr's "ON + 16*UNK" sum over the window

  // classicDefault: a rule with no B/S letters is read the way dr2.c reads
  // it ("3/23" = B3/S23) instead of the Golly way ("23/3" = B3/S23).
  bool parse(const std::string &s, std::string &err, bool classicDefault = false);
  void build();
  bool isTotalistic() const;
  bool invariantUnder(int symm) const;
  std::string canonical() const;   // B../S.. (Hensel letters if needed) or MAP
  std::string mapString() const;   // Golly MAP form (works for every rule)
};

}  // namespace drift
