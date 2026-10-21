// Named options. Each option works on the command line (--name value or
// --name=value) and in a config file (name = value, one per line). Region and
// position arguments are relative to the top-left cell of the pattern.
#include "options.h"

#include <algorithm>
#include <cctype>
#include <climits>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <sstream>
#include <stdexcept>

namespace drift {

namespace {

struct RegionSpec { PatternOp::Kind kind; int bit; std::string text; };

struct Ctx {
  Options &o;
  explicit Ctx(Options &opt) : o(opt) {}
  std::string patternText, patternSource;
  int margin = 30, gridH = 0, gridW = 0;
  bool symmFromSet = false;
  long symmFrom = 0;
  std::vector<RegionSpec> regions;
  bool persistRegionSet = false;
  Region persistRegion;
  bool pushRight = false, pushDown = false, pushDownC2 = false;
  bool help = false;
  std::vector<Params::Push> pushes;   // k still pattern-relative
  bool uncheckedBorder = false;
  std::string baseDir;   // directory of the config file, for relative paths
};

struct Opt {
  const char *name, *arg, *group, *help;
  std::function<void(Ctx &, const std::string &)> set;
};

[[noreturn]] void fail(const std::string &msg) { throw std::runtime_error(msg); }

long toLong(const std::string &name, const std::string &v) {
  char *end;
  long x = strtol(v.c_str(), &end, 10);
  while (*end == ' ') end++;
  if (v.empty() || *end) fail("--" + name + " expects a whole number, got '" + v + "'");
  return x;
}

long toLong(const std::string &name, const std::string &v, long min) {
  long x = toLong(name, v);
  if (x < min) fail("--" + name + " must be at least " + std::to_string(min) + ", got " + v);
  return x;
}

std::vector<long> toLongs(const std::string &name, const std::string &v, size_t n) {
  std::vector<long> out;
  std::istringstream in(v);
  std::string tok;
  while (in >> tok) {
    for (char &ch : tok) if (ch == ',') ch = ' ';
    std::istringstream in2(tok);
    std::string t2;
    while (in2 >> t2) out.push_back(toLong(name, t2));
  }
  if (n && out.size() != n)
    fail("--" + name + " expects " + std::to_string(n) + " numbers, got '" + v + "'");
  return out;
}

bool toBool(const std::string &name, const std::string &v) {
  if (v.empty() || v == "1" || v == "yes" || v == "true" || v == "on") return true;
  if (v == "0" || v == "no" || v == "false" || v == "off") return false;
  fail("--" + name + " expects yes or no, got '" + v + "'");
}

std::string readFile(const std::string &path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) fail("can't open '" + path + "'");
  std::stringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

std::string resolve(const Ctx &c, const std::string &path) {
  if (path.empty() || path[0] == '/' || c.baseDir.empty()) return path;
  return c.baseDir + "/" + path;
}

int parseSymm(const std::string &v) {
  static const struct { const char *n; int s; } names[] = {
    {"none", NOSYMM}, {"no", NOSYMM}, {"nosymm", NOSYMM},
    {"hor", HORSYMM}, {"horizontal", HORSYMM}, {"horsymm", HORSYMM},
    {"vert", VERTSYMM}, {"vertical", VERTSYMM}, {"vertsymm", VERTSYMM},
    {"diag", DIAGSYMM}, {"diagonal", DIAGSYMM}, {"diagsymm", DIAGSYMM},
    {"rot90", ROT90SYMM}, {"rot90symm", ROT90SYMM},
    {"rot180", ROT180SYMM}, {"rot180symm", ROT180SYMM},
    {"plus", PLUSSYMM}, {"plussymm", PLUSSYMM},
    {"x", XSYMM}, {"xsymm", XSYMM},
    {"full", FULLSYMM}, {"fullsymm", FULLSYMM},
  };
  for (auto &n : names)
    if (v == n.n) return n.s;
  fail("unknown symmetry '" + v + "' (use none, hor, vert, diag, rot90, rot180, plus, x or full)");
}

void region(Ctx &c, PatternOp::Kind kind, int bit, const std::string &v) {
  Region reg;
  std::string err;
  if (!parseRegion(v, reg, 'r', err)) fail(err);   // validate now, place later
  c.regions.push_back({kind, bit, v});
}

#define VAR(n) [](Ctx &c, const std::string &v) { c.o.params.var[n] = toLong(#n, v); }

const std::vector<Opt> &opts() {
  static const std::vector<Opt> list = {
    // --- What to search
    {"rule", "RULE", "Search",
     "Rule: B3/S23, an INT rule like B2-a3/S12, or a Golly MAP string. Default B3/S23.",
     [](Ctx &c, const std::string &v) {
       std::string err;
       if (!c.o.rule.parse(v, err)) fail("bad rule '" + v + "': " + err);
       c.o.ruleSet = true;
     }},
    {"pattern", "FILE", "Search",
     "Starting pattern: a LifeHistory RLE (0 unknown, 1 on, 2 known off, 3 on in gen 0 only,\n"
     "4 off in gen 0 only, 5 on and may not change, 6 off and may not change) or dr2.c's\n"
     "character grid (o . 0 1 ? : O s 2 3 4). In a config file it can also be given inline\n"
     "as 'pattern:' followed by the pattern lines.",
     [](Ctx &c, const std::string &v) {
       c.patternText = readFile(resolve(c, v));
       c.patternSource = v;
     }},
    {"max-changed", "N", "Search", "Max number of changed cells in a generation (dr2: c). Default 9.",
     [](Ctx &c, const std::string &v) { c.o.params.maxchng = (int)toLong("max-changed", v, 1); }},
    {"max-width", "N", "Search", "Max width of the changed region (dr2: w). Default 3.",
     [](Ctx &c, const std::string &v) { c.o.params.maxwidth = (int)toLong("max-width", v, 1); }},
    {"max-height", "N", "Search", "Max height of the changed region (dr2: h). Default 3.",
     [](Ctx &c, const std::string &v) { c.o.params.maxheight = (int)toLong("max-height", v, 1); }},
    {"size", "WxH", "Search", "Shorthand for --max-width W --max-height H.",
     [](Ctx &c, const std::string &v) {
       int w, h;
       std::string t = v;
       for (char &ch : t) if (ch == 'X' || ch == '*') ch = 'x';
       if (sscanf(t.c_str(), "%dx%d", &w, &h) != 2) fail("--size expects WxH, e.g. 5x3");
       if (w < 1 || h < 1) fail("--size: width and height must be at least 1, got " + v);
       c.o.params.maxwidth = w;
       c.o.params.maxheight = h;
     }},
    {"max-gen", "N", "Search", "Report 'max gen reached' at this generation. Default 500.",
     [](Ctx &c, const std::string &v) { c.o.params.maxgen = (int)toLong("max-gen", v); }},
    {"symmetry", "S", "Search",
     "Background symmetry: none, hor, vert, diag, rot90, rot180, plus, x, full. The centre\n"
     "is the centre of the pattern. Only the background is symmetric, not gen 0.",
     [](Ctx &c, const std::string &v) { c.o.params.symm = parseSymm(v); }},
    {"symmetry-from", "N", "Search",
     "With hor (vert) symmetry, only mirror columns (rows) >= N, counted from the pattern.",
     [](Ctx &c, const std::string &v) { c.symmFromSet = true; c.symmFrom = toLong("symmetry-from", v); }},
    {"day-night", nullptr, "Search", "Mirror cells with opposite values (hor, vert, rot180 only).",
     [](Ctx &c, const std::string &v) { c.o.params.var[130] = toBool("day-night", v); }},
    {"margin", "N", "Search", "Unknown cells around the pattern on each side. Default 30.",
     [](Ctx &c, const std::string &v) { c.margin = (int)toLong("margin", v, 0); }},
    {"grid", "HxW", "Search", "Use a fixed H x W space (pattern centred) instead of --margin.",
     [](Ctx &c, const std::string &v) {
       std::string t = v;
       for (char &ch : t) if (ch == 'X' || ch == '*') ch = 'x';
       if (sscanf(t.c_str(), "%dx%d", &c.gridH, &c.gridW) != 2) fail("--grid expects HxW, e.g. 81x81");
     }},
    {"unchecked-border", nullptr, "Search",
     "Don't require the space's dead border to be stable (dr2.c's behaviour; results that\n"
     "reach the edge may then be impossible to complete).",
     [](Ctx &c, const std::string &v) { c.uncheckedBorder = toBool("unchecked-border", v); }},
    {"seed", "N", "Search", "Random seed for the order in which choices are tried. Default 1.",
     [](Ctx &c, const std::string &v) { c.o.params.seed = (unsigned)toLong("seed", v); }},
    {"prob", "PERCENT", "Search", "Chance of trying ON first at each free choice. Default 50.",
     [](Ctx &c, const std::string &v) { c.o.params.prob = (int)toLong("prob", v); }},

    // --- Regions
    {"clear", "REGION", "Regions",
     "Set unknown background cells in the region to OFF. REGION is 'r R0 C0 R1 C1'\n"
     "(rectangle), 'l R0 C0 R1 C1' (line), 'p R C' (point) or 't R0 C0 R1 C1 R2 C2'\n"
     "(triangle), in rows/columns from the pattern's top-left cell; negative is fine.",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::CLEAR, 0, v); }},
    {"no-change", "REGION", "Regions", "Cells in the region may never change (dr2: d0).",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::SETFLAG, 0, v); }},
    {"allow-change", "REGION", "Regions", "Undo --no-change in the region (dr2: D0).",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::CLEARFLAG, 0, v); }},
    {"no-count", "REGION", "Regions",
     "Changes in the region don't count towards the size limits (dr2: d1). Useful for\n"
     "eaters; results ending with only these cells changed are 'semifizzles'.",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::SETFLAG, 1, v); }},
    {"count", "REGION", "Regions", "Undo --no-count in the region (dr2: D1).",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::CLEARFLAG, 1, v); }},
    {"no-check", "REGION", "Regions",
     "Don't require the background to be stable in the region (dr2: d2 / '4' cells).",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::SETFLAG, 2, v); }},
    {"check", "REGION", "Regions", "Undo --no-check in the region (dr2: D2).",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::CLEARFLAG, 2, v); }},
    {"must-reach", "REGION", "Regions",
     "Only report results in which some cell in one of these regions changes (e.g. an\n"
     "output spark appearing in empty space). May be given several times.",
     [](Ctx &c, const std::string &v) { region(c, PatternOp::SETFLAG, 3, v); c.o.mustReach = true; }},

    // --- Extra constraints (dr2.c's v100..v139)
    {"change-counts", "N,N,...", "Constraints",
     "Exact change counts for gens 0, 1, ...; a negative N means 'anything but -N' (dr2: cc).",
     [](Ctx &c, const std::string &v) {
       c.o.params.reqchgcount.clear();
       for (long x : toLongs("change-counts", v, 0)) c.o.params.reqchgcount.push_back((int)x);
     }},
    {"min-changed", "N", "Constraints", "Lower bound on the change count, when non-zero (v120).", VAR(120)},
    {"relax-changed", "N", "Constraints",
     "Only require the change count limit once in every N consecutive gens (v100).", VAR(100)},
    {"relax-height", "N", "Constraints", "Same for the height limit (v125).", VAR(125)},
    {"relax-width", "N", "Constraints", "Same for the width limit (v126).", VAR(126)},
    {"max-new-changed", "N", "Constraints",
     "Max cells changed this gen that weren't changed the gen before (v101).", VAR(101)},
    {"max-new-changed-vs", "N,G", "Constraints",
     "Max cells changed this gen that weren't changed G gens ago (v117, v118).",
     [](Ctx &c, const std::string &v) {
       auto x = toLongs("max-new-changed-vs", v, 2);
       c.o.params.var[117] = x[0];
       c.o.params.var[118] = x[1];
     }},
    {"diag-width-ne", "N", "Constraints", "Bound on the changed region's NE-SW diagonal width (v102).", VAR(102)},
    {"diag-width-nw", "N", "Constraints", "Bound on the changed region's NW-SE diagonal width (v103).", VAR(103)},
    {"push", "DIR SPEED [SLACK]", "Constraints",
     "Make the disturbance keep moving: every newly changed cell must be at least\n"
     "SPEED*gen - SLACK cells beyond where the disturbance started (the gen-0 changed\n"
     "cells' trailing edge) in direction DIR (right, left,\n"
     "up, down, a diagonal ne/nw/se/sw where both coordinates must keep up, or a vector\n"
     "R,C for oblique motion: SPEED c/N then means R rows down and C columns right every\n"
     "N gens). SPEED like c/2, 2c/3, c/4, or 0 (don't fall more than SLACK behind in that\n"
     "direction; use two opposite ones to keep to a line). SLACK defaults to 2.\n"
     "E.g. --push \"right c/2 3\", --push \"1,2 c/6\".",
     [](Ctx &c, const std::string &v) {
       std::istringstream in(v);
       std::string dir, speed;
       long slack = 2;
       in >> dir >> speed;
       if (!(in >> slack)) slack = 2;
       long num = 1, den = 1;
       size_t cpos = speed.find('c');
       if (speed == "0") { num = 0; cpos = std::string::npos - 1; }   // stay within SLACK
       else
       if (cpos == std::string::npos) fail("--push: speed must look like c/2 or 2c/3");
       if (num && cpos > 0) num = toLong("push", speed.substr(0, cpos));
       if (num && cpos + 1 < speed.size()) {
         if (speed[cpos + 1] != '/') fail("--push: speed must look like c/2 or 2c/3");
         den = toLong("push", speed.substr(cpos + 2));
       }
       if (num < 0 || den <= 0 || num > den) fail("--push: speed must be between 0 and c");
       int vr, vc;
       if (sscanf(dir.c_str(), "%d,%d", &vr, &vc) == 2) {   // oblique: project on (vr,vc)
         if (!vr && !vc) fail("--push: zero direction");
         long len2 = (long)vr * vr + (long)vc * vc;
         c.pushes.push_back({vr, vc, num * len2, den, -den * slack * (labs(vr) + labs(vc))});
         return;
       }
       int dr = 0, dcol = 0;
       if (dir != "up" && dir != "down" && dir != "left" && dir != "right" &&
           (dir.empty() || dir.find_first_not_of("nsew") != std::string::npos))
         fail("--push: unknown direction '" + dir + "' (use up, down, left, right, n, ne, sw, ... or R,C)");
       for (char ch : dir) {
         if (ch == 'n' || dir == "up") dr = -1;
         if (ch == 's' || dir == "down") dr = 1;
         if (ch == 'e' || dir == "right") dcol = 1;
         if (ch == 'w' || dir == "left") dcol = -1;
       }
       if (dir == "up") dcol = 0, dr = -1;
       if (dir == "down") dcol = 0, dr = 1;
       if (dir == "right") dr = 0, dcol = 1;
       if (dir == "left") dr = 0, dcol = -1;
       if (!dr && !dcol) fail("--push: unknown direction '" + dir + "'");
       if (dr) c.pushes.push_back({dr, 0, num, den, -den * slack});
       if (dcol) c.pushes.push_back({0, dcol, num, den, -den * slack});
     }},
    {"push-right", "K", "Constraints",
     "Force a signal moving right at >= 2c/3: changed cells need 3*col >= 2*gen + K,\n"
     "col counted from the pattern's left edge (v104).",
     [](Ctx &c, const std::string &v) { c.o.params.var[104] = toLong("push-right", v); c.pushRight = true; }},
    {"push-down", "K", "Constraints", "Same, moving down at >= 2c/3 (v105).",
     [](Ctx &c, const std::string &v) { c.o.params.var[105] = toLong("push-down", v); c.pushDown = true; }},
    {"push-down-c2", "K", "Constraints", "Moving down at >= c/2: 2*row >= gen + K (v109).",
     [](Ctx &c, const std::string &v) { c.o.params.var[109] = toLong("push-down-c2", v); c.pushDownC2 = true; }},
    {"count-from-gen", "G", "Constraints", "Ignore changes before gen G when checking limits (v106).",
     [](Ctx &c, const std::string &v) { c.o.params.var[106] = toLong("count-from-gen", v, 0); }},
    {"no-rechange", "A,B", "Constraints",
     "A cell may not be changed in two gens between A and B gens apart (v107, v108). Keeps the "
     "disturbance moving onto fresh cells, at any speed and in any direction: e.g. 8,80 for drifters. "
     "Oscillators end soon after they start repeating.",
     [](Ctx &c, const std::string &v) {
       auto x = toLongs("no-rechange", v, 2);
       if (!(x[0] == 0 && x[1] == 0) && (x[0] < 1 || x[1] < x[0])) fail("--no-rechange A,B needs 1 <= A <= B (or 0,0 for off), got '" + v + "'");
       c.o.params.var[107] = x[0];
       c.o.params.var[108] = x[1];
     }},
    {"max-twos", "N", "Constraints", "Allow change count 2 in at most N consecutive gens (v110).", VAR(110)},
    {"persist", "N", "Constraints",
     "Gen g changes inside --persist-region must still be present in gen g+N (v111).", VAR(111)},
    {"persist-region", "R0 C0 R1 C1", "Constraints", "Rectangle for --persist (v132..v135).",
     [](Ctx &c, const std::string &v) {
       auto x = toLongs("persist-region", v, 4);
       std::string err;
       parseRegion("r " + v, c.persistRegion, 'r', err);
       c.persistRegionSet = true;
     }},
    {"split-vertical", nullptr, "Constraints",
     "The changed region may be two pieces, each at most --max-height tall (v112).",
     [](Ctx &c, const std::string &v) { c.o.params.var[112] = toBool("split-vertical", v); }},
    {"split-horizontal", nullptr, "Constraints",
     "The changed region may be two pieces, each at most --max-width wide (v113).",
     [](Ctx &c, const std::string &v) { c.o.params.var[113] = toBool("split-horizontal", v); }},
    {"forbid-5c9", nullptr, "Constraints", "Stop when the 5c/9 signal repeats for 19 gens (v116).",
     [](Ctx &c, const std::string &v) { c.o.params.var[116] = toBool("forbid-5c9", v); }},
    {"fizzle-gen0-only", nullptr, "Constraints",
     "Only look up known fizzlers at gen 0 (use when not starting from known signals) (v119).",
     [](Ctx &c, const std::string &v) { c.o.params.var[119] = toBool("fizzle-gen0-only", v); }},
    {"forbid-count", "G,N", "Constraints", "Change count in gen G may not be N (v121, v122).",
     [](Ctx &c, const std::string &v) {
       auto x = toLongs("forbid-count", v, 2);
       c.o.params.var[121] = x[0];
       c.o.params.var[122] = x[1];
     }},
    {"require-count", "G,N", "Constraints",
     "Change count must be N before gen G, and not N at gen G (v123, v124).",
     [](Ctx &c, const std::string &v) {
       auto x = toLongs("require-count", v, 2);
       c.o.params.var[123] = x[0];
       c.o.params.var[124] = x[1];
     }},
    {"pattern-no-count", nullptr, "Constraints",
     "Cells given in the pattern don't count towards the size limits (v127).",
     [](Ctx &c, const std::string &v) { c.o.params.var[127] = toBool("pattern-no-count", v); }},
    {"same-shape-every", "P", "Constraints",
     "Change count and bounding box must match the ones P gens earlier (v128).", VAR(128)},
    {"max-age-sum", "N", "Constraints", "Bound on the sum of ages of changed cells (v129).", VAR(129)},
    {"max-consec-sum", "K,G", "Constraints",
     "Bound K on the summed run lengths of changed cells, runs bridging gaps of up to G gens\n"
     "(v137, v138).",
     [](Ctx &c, const std::string &v) {
       auto x = toLongs("max-consec-sum", v, 2);
       c.o.params.var[137] = x[0];
       c.o.params.var[138] = x[1];
     }},
    {"max-neighbors", "N", "Constraints", "Bound on the number of neighbours of changed cells (v139).", VAR(139)},
    {"var", "N,V", "Constraints", "Set dr2.c variable N to V directly (absolute coordinates).",
     [](Ctx &c, const std::string &v) {
       auto x = toLongs("var", v, 2);
       if (x[0] < 0 || x[0] >= NUMVARS) fail("--var: no variable " + std::to_string(x[0]));
       c.o.params.var[x[0]] = x[1];
     }},

    // --- Output
    {"only-new", nullptr, "Output", "Don't print outcomes whose rotor is in the known rotors list.",
     [](Ctx &c, const std::string &v) { c.o.skipKnown = toBool("only-new", v); }},
    {"skip", "KINDS", "Output", "Don't print these outcomes: any of oscillator, stable, fizzle, maxgen.",
     [](Ctx &c, const std::string &v) {
       std::string s = v;
       for (char &ch : s) if (ch == ',') ch = ' ';
       std::istringstream in(s);
       std::string k;
       while (in >> k) {
         if (k == "oscillator" || k == "periodic" || k == "oscillators") c.o.skipPeriodic = true;
         else if (k == "stable") c.o.skipStable = true;
         else if (k == "fizzle" || k == "fizzles") c.o.skipFizzle = true;
         else if (k == "maxgen") c.o.skipMaxgen = true;
         else fail("--skip: unknown kind '" + k + "'");
       }
     }},
    {"skip-stable", nullptr, "Output", "Same as --skip stable (dr2: skipstable).",
     [](Ctx &c, const std::string &v) { c.o.skipStable = toBool("skip-stable", v); }},
    {"skip-fizzle", nullptr, "Output", "Same as --skip fizzle (dr2: skipfizzle).",
     [](Ctx &c, const std::string &v) { c.o.skipFizzle = toBool("skip-fizzle", v); }},
    {"max-results", "N", "Output",
     "Stop printing after N results (the search continues and keeps counting).\n"
     "Default 10000; 0 = no limit.",
     [](Ctx &c, const std::string &v) { c.o.maxResults = toLong("max-results", v); }},
    {"per-rotor", "N", "Output",
     "Print at most N results with the same rotor (history for fizzles; for max-gen results,\n"
     "the same change counts over the last 30 gens). Default 10; 0 = no limit.",
     [](Ctx &c, const std::string &v) { c.o.perRotor = (int)toLong("per-rotor", v); }},
    {"min-period", "P", "Output", "Don't print oscillators with period below P.",
     [](Ctx &c, const std::string &v) { c.o.minPeriod = (int)toLong("min-period", v); }},
    {"no-pics", nullptr, "Output", "Don't print the character pictures.",
     [](Ctx &c, const std::string &v) { c.o.noPics = toBool("no-pics", v); }},
    {"no-rle", nullptr, "Output", "Don't print RLE.",
     [](Ctx &c, const std::string &v) { c.o.noRle = toBool("no-rle", v); }},
    {"show-final", nullptr, "Output", "Also show the final generation (dr2: showfin).",
     [](Ctx &c, const std::string &v) { c.o.showFin = toBool("show-final", v); }},
    {"show-all", nullptr, "Output", "Show every generation (dr2: showall).",
     [](Ctx &c, const std::string &v) { c.o.showAll = toBool("show-all", v); }},
    {"known-rotors", "FILE", "Output",
     "Known rotors list. By default dr2.c's 'knownrotors' file is used for B3/S23 only.",
     [](Ctx &c, const std::string &v) { c.o.knownRotorsFile = resolve(c, v); c.o.knownRotorsExplicit = true; }},
    {"jsonl", "FILE", "Output",
     "Append each result to FILE as one JSON object per line (instead of <config>-results.jsonl).",
     [](Ctx &c, const std::string &v) { c.o.jsonl = v; }},
    {"out", "FILE", "Output",
     "Append the printed results to FILE (instead of <config>-results.txt). With a config\n"
     "file, results are saved to <config>-results.txt and <config>-results.jsonl by default.",
     [](Ctx &c, const std::string &v) { c.o.textOut = v; }},
    {"no-save", nullptr, "Output", "Don't save results to files by default.",
     [](Ctx &c, const std::string &v) { c.o.noSave = toBool("no-save", v); }},
    {"no-finish", nullptr, "Output",
     "Don't run tools/finish.py after the search (it turns the results into complete,\n"
     "checked patterns in <config>-finished.txt).",
     [](Ctx &c, const std::string &v) { c.o.noFinish = toBool("no-finish", v); }},
    {"quiet", nullptr, "Output", "No progress line on stderr.",
     [](Ctx &c, const std::string &v) { c.o.quiet = toBool("quiet", v); }},
    {"progress", "SECONDS", "Output", "Progress line interval. Default 10.",
     [](Ctx &c, const std::string &v) { c.o.progressEvery = (double)toLong("progress", v); }},

    // --- Running
    {"threads", "N", "Run", "Worker threads. Default: all cores.",
     [](Ctx &c, const std::string &v) { c.o.threads = (int)toLong("threads", v, 0); }},
    {"checkpoint", "FILE", "Run",
     "Save resumable state to FILE every --checkpoint-every seconds and on Ctrl-C.",
     [](Ctx &c, const std::string &v) { c.o.checkpoint = v; }},
    {"checkpoint-every", "SECONDS", "Run", "Default 300.",
     [](Ctx &c, const std::string &v) { c.o.checkpointEvery = (double)toLong("checkpoint-every", v); }},
    {"resume", "FILE", "Run", "Continue the run saved in FILE (other options may be added).",
     [](Ctx &c, const std::string &v) { c.o.resume = v; }},
    {"max-steps", "N", "Run", "Stop after about N search steps (for timing or a quick look).",
     [](Ctx &c, const std::string &v) { c.o.maxSteps = toLong("max-steps", v); }},
    {"max-time", "SECONDS", "Run",
     "Stop after this many seconds (with --checkpoint, the rest of the search is saved and can be "
     "resumed).",
     [](Ctx &c, const std::string &v) { c.o.maxTime = (double)toLong("max-time", v, 0); }},
    {"threads-file", "FILE", "Run",
     "Read the number of threads to use from FILE every second, so it can be changed while the "
     "search runs (tools/survey.py uses this to move cores between searches). --threads (default: "
     "all cores) is then the most it can use.",
     [](Ctx &c, const std::string &v) { c.o.threadsFile = v; }},
    {"dry-run", nullptr, "Run", "Set everything up, show the starting position and exit.",
     [](Ctx &c, const std::string &v) { c.o.dryRun = toBool("dry-run", v); }},
    {"show-rule", nullptr, "Run", "Print the rule in canonical and MAP form and exit.",
     [](Ctx &c, const std::string &v) { c.o.showRule = toBool("show-rule", v); }},
    {"help", nullptr, "Run", "Show this help.",
     [](Ctx &c, const std::string &) { c.help = true; }},
  };
  return list;
}

const Opt *findOpt(const std::string &name) {
  for (const Opt &o : opts())
    if (name == o.name) return &o;
  return nullptr;
}

std::string trim(const std::string &s) {
  size_t a = 0, b = s.size();
  while (a < b && isspace((unsigned char)s[a])) a++;
  while (b > a && isspace((unsigned char)s[b - 1])) b--;
  return s.substr(a, b - a);
}

void apply(Ctx &c, const std::string &name, const std::string &value, const std::string &where) {
  const Opt *o = findOpt(name);
  if (!o) fail(where + "unknown option '" + name + "' (see --help)");
  if (o->arg && value.empty()) fail(where + "--" + name + " needs a value (" + o->arg + ")");
  o->set(c, value);
}

void readConfig(Ctx &c, const std::string &path) {
  std::string text = readFile(path);
  size_t slash = path.rfind('/');
  std::string saved = c.baseDir;
  c.baseDir = slash == std::string::npos ? "" : path.substr(0, slash);
  std::istringstream in(text);
  std::string line;
  int lineno = 0;
  while (std::getline(in, line)) {
    lineno++;
    std::string where = path + ":" + std::to_string(lineno) + ": ";
    std::string t = trim(line);
    if (t.empty() || t[0] == '#' || t[0] == ';') continue;
    for (size_t k = 1; k < t.size(); k++)   // trailing "# comment"
      if (t[k] == '#' && isspace((unsigned char)t[k - 1])) { t = trim(t.substr(0, k)); break; }
    if (t == "pattern:" || t == "pattern =" || t == "pattern=") {   // inline pattern block
      std::string block;
      while (std::getline(in, line)) {
        lineno++;
        block += line + "\n";
        if (line.find('!') != std::string::npos) break;
      }
      c.patternText = block;
      c.patternSource = path;
      continue;
    }
    size_t eq = t.find('=');
    size_t sp = t.find_first_of(" \t");
    std::string name, value;
    if (eq != std::string::npos && (sp == std::string::npos || eq < sp ||
                                    trim(t.substr(sp, eq - sp)).empty())) {
      name = trim(t.substr(0, eq));
      value = trim(t.substr(eq + 1));
    } else if (sp != std::string::npos) {
      name = t.substr(0, sp);
      value = trim(t.substr(sp));
    } else
      name = t;
    if (name.size() > 2 && name.compare(0, 2, "--") == 0) name = name.substr(2);
    apply(c, name, value, where);
  }
  c.baseDir = saved;
}

}  // namespace

std::vector<std::string> loadPatternText(const std::string &text) {
  std::vector<std::string> rawlines;
  {
    std::istringstream in(text);
    std::string line;
    while (std::getline(in, line)) {
      if (!line.empty() && line.back() == '\r') line.pop_back();
      std::string t = trim(line);
      if (t.empty() && rawlines.empty()) continue;
      if (!t.empty() && (t[0] == '#' || t[0] == ';')) continue;
      rawlines.push_back(line);
      if (line.find('!') != std::string::npos) break;
    }
  }
  bool rle = false;
  for (const std::string &l : rawlines) {
    std::string t = trim(l);
    if (t.size() > 1 && t[0] == 'x' && trim(t.substr(1)).compare(0, 1, "=") == 0) rle = true;
    if (l.find('$') != std::string::npos) rle = true;
  }
  if (rawlines.empty() || rawlines.back().find('!') == std::string::npos)
    fail("pattern must end with '!'");

  if (!rle) {   // dr2.c's characters
    for (std::string &l : rawlines) {
      size_t a = 0;
      while (a < l.size() && (l[a] == ' ' || l[a] == '\t')) a++;
      l = l.substr(a);
    }
    return rawlines;
  }

  // LifeHistory (or two-state) RLE
  static const char MAP[] = ",o.10O:";   // state -> dr2.c character
  std::vector<std::string> rows(1);
  size_t start = 0;
  for (; start < rawlines.size(); start++) {
    std::string t = trim(rawlines[start]);
    if (!(t.size() > 1 && t[0] == 'x' && trim(t.substr(1)).compare(0, 1, "=") == 0)) break;
  }
  long run = 0;
  bool done = false;
  for (size_t li = start; li < rawlines.size() && !done; li++)
    for (char ch : rawlines[li]) {
      if (isdigit((unsigned char)ch)) { run = run * 10 + (ch - '0'); continue; }
      if (isspace((unsigned char)ch)) continue;
      long n = run ? run : 1;
      run = 0;
      int state = -1;
      if (ch == 'b' || ch == '.') state = 0;
      else if (ch == 'o') state = 1;
      else if (ch >= 'A' && ch <= 'F') state = ch - 'A' + 1;
      else if (ch == '$') { for (long k = 0; k < n; k++) rows.emplace_back(); continue; }
      else if (ch == '!') { done = true; break; }
      else fail(std::string("unexpected '") + ch + "' in RLE (LifeHistory states 0-6 only)");
      rows.back().append((size_t)n, MAP[state]);
    }
  rows.back() += '!';
  return rows;
}

void printHelp() {
  printf(
      "drift: search for drifters (perturbations that move through an unknown\n"
      "stable background) in Life-like, INT and MAP rules.\n"
      "A port of Dean Hickerson's dr2.c.\n\n"
      "Usage:\n"
      "  drift CONFIG [--option value ...]      search, then finish the results\n"
      "  drift --resume run.ckpt                continue a saved search\n"
      "  drift --classic < dr2-input-file       run an old dr2.c input file\n"
      "  drift survey RULE [--minutes M]        many searches at once in RULE, sharing the cores;\n"
      "                                         writes surveys/RULE/SUMMARY.md (survey --help)\n"
      "  drift finish CONFIG                    complete and check results (also: render,\n"
      "                                         validate, wirecheck, wirebuild)\n\n"
      "CONFIG is a file of 'option = value' lines (# starts a comment) ending with the\n"
      "pattern after a 'pattern:' line; see docs/GUIDE.md. Options on the command line\n"
      "override the file. Results go to CONFIG-results.txt / .jsonl, and complete,\n"
      "checked patterns to CONFIG-finished.txt.\n"
      "Exit status: 0 when the search completes or stops at a limit you set (--max-time,\n"
      "--max-steps; the footer says which), 130 after Ctrl-C, 1 on an error.\n");
  static const char *ORDER[] = {"Search", "Regions", "Output", "Run", "Constraints"};
  for (const char *group : ORDER) {
    printf("\n%s:\n", strcmp(group, "Constraints") == 0 ? "Advanced constraints (dr2.c's v100..v139)" : group);
    for (const Opt &o : opts()) {
    if (strcmp(o.group, group) != 0) continue;
    std::string head = std::string("  --") + o.name + (o.arg ? std::string(" ") + o.arg : "");
    printf("%-28s", head.c_str());
    if (head.size() > 27) printf("\n%28s", "");
    // word-wrap the help to 72 columns (100 in all)
    std::string h = o.help, line;
    std::replace(h.begin(), h.end(), '\n', ' ');
    h += "\n";
    bool first = true;
    auto flush = [&] {
      printf(first ? "%s\n" : "%28s%s\n", first ? line.c_str() : "", line.c_str());
      first = false;
      line.clear();
    };
    size_t i = 0;
    while (i < h.size()) {
      size_t j = h.find_first_of(" \n", i);
      std::string word = h.substr(i, j - i);
      if (!line.empty() && line.size() + 1 + word.size() > 72) flush();
      if (!word.empty()) line += (line.empty() ? "" : " ") + word;
      if (h[j] == '\n') flush();
      i = j + 1;
    }
    }
  }
  printf("\nExample: drift examples/beehive-spark.cfg\n");
}

bool readModern(const std::vector<std::string> &args, Options &o) {
  Ctx c(o);
  for (size_t i = 0; i < args.size(); i++) {
    const std::string &a = args[i];
    if (a.size() > 2 && a.compare(0, 2, "--") == 0) {
      std::string name = a.substr(2), value;
      size_t eq = name.find('=');
      if (eq != std::string::npos) {
        value = name.substr(eq + 1);
        name = name.substr(0, eq);
      } else {
        const Opt *opt = findOpt(name);
        if (opt && opt->arg) {
          if (i + 1 >= args.size()) fail("--" + name + " needs a value (" + opt->arg + ")");
          value = args[++i];
        }
      }
      apply(c, name, value, "");
    } else if (a == "-h")
      c.help = true;
    else {
      if (i > 0 && args[i - 1].compare(0, 2, "--") == 0 && args[i - 1].find('=') == std::string::npos) {
        const Opt *prev = findOpt(args[i - 1].substr(2));
        std::ifstream probe(a);
        if (prev && !prev->arg && !probe)
          fail(args[i - 1] + " doesn't take a value (to turn it off, write " + args[i - 1] + "=no)");
      }
      readConfig(c, a);
      o.configPath = a;
    }
  }
  if (c.help) {
    printHelp();
    return false;
  }
  if (!o.resume.empty()) return true;   // finished by the resume code

  Params &P = o.params;
  if (!o.ruleSet) {
    std::string err;
    o.rule.parse("B3/S23", err);
  }
  if (o.showRule) {
    printf("canonical: %s\nMAP:       %s\n%s, %s\n", o.rule.canonical().c_str(),
           o.rule.mapString().c_str(), o.rule.isTotalistic() ? "outer-totalistic" : "not totalistic",
           o.rule.invariantUnder(FULLSYMM) ? "isotropic" : "not isotropic");
    return false;
  }
  if (c.patternText.empty()) fail("no pattern given (use --pattern FILE; see --help)");
  std::vector<std::string> lines = loadPatternText(c.patternText);
  // drift reads RLE as LifeHistory: in a two-state RLE (Golly's copy of a plain
  // pattern) every 'b' cell is unknown, not dead, and there is no spark.
  std::string twoState;
  {
    std::istringstream in(c.patternText);
    std::string l;
    while (std::getline(in, l)) {
      size_t p = l.find("rule");
      if (trim(l).compare(0, 1, "x") != 0 || p == std::string::npos) continue;
      std::string r = trim(l.substr(l.find('=', p) + 1));
      std::string lower;
      for (char ch : r) lower += (char)tolower((unsigned char)ch);
      if (lower.find("history") == std::string::npos) twoState = r;
      break;
    }
  }
  if (!twoState.empty())
    o.warnings.push_back("the pattern's RLE header says rule = " + twoState + ", but drift reads patterns "
                         "as LifeHistory: 'b' cells are unknown, not dead. Draw the pattern in Golly with "
                         "the LifeHistory rule (dead cells in state 2, the spark in state 3).");
  int ph = (int)lines.size(), pw = 0;
  bool anyChange = false;
  for (const std::string &l : lines) {
    int w = 0;
    for (char ch : l) {
      if (ch == '!') break;
      if (ch != '\r') w++;
      if (ch == '0' || ch == '1' || ch == '2' || ch == '3' || ch == '4') anyChange = true;
    }
    pw = std::max(pw, w);
  }
  if (!anyChange)
    fail("the pattern has no cells that differ in gen 0. Mark them with LifeHistory state 3\n"
         "(on in gen 0, off in the background) or 4 (the reverse), or dr2.c's '1' / '0'\n"
         "(or start from unchecked cells: dr2.c's '2' / '3' / '4')." +
         (twoState.empty() ? std::string()
                           : "\nThis RLE is a two-state pattern (rule = " + twoState +
                                 "): draw it in Golly with the LifeHistory rule instead."));

  bool square = P.symm == DIAGSYMM || P.symm == ROT90SYMM || P.symm == XSYMM || P.symm == FULLSYMM;
  if (c.gridH) {
    P.HT = c.gridH;
    P.WD = c.gridW;
    if (P.HT < ph + 4 || P.WD < pw + 4) fail("--grid is too small for the pattern");
    if (square && P.HT != P.WD) fail("--grid must be square (H = W) for this symmetry");
  } else {
    P.HT = ph + 2 * c.margin + 4;
    P.WD = pw + 2 * c.margin + 4;
    if (square) P.HT = P.WD = std::max(P.HT, P.WD);
  }
  o.top = (P.HT - ph) / 2;
  o.left = (P.WD - pw) / 2;
  o.patHeight = ph;
  o.patWidth = pw;
  if (P.symm != NOSYMM && ((P.HT - ph) % 2 || (P.WD - pw) % 2))
    o.warnings.push_back("the symmetry centre is half a cell off the pattern's centre "
                         "(pattern and grid sizes differ in parity)");
  if (!o.rule.invariantUnder(P.symm))
    o.warnings.push_back("the rule is not invariant under the chosen symmetry; the "
                         "background will satisfy both the rule and its mirror image");

  // Region flags first (so DONTCHECK cells are flagged before the pattern is
  // read, which dr2.c requires), then the pattern, then clears.
  for (const RegionSpec &rs : c.regions) {
    if (rs.kind == PatternOp::CLEAR) continue;
    PatternOp op;
    op.kind = rs.kind;
    op.bit = rs.bit;
    std::string err;
    parseRegion(rs.text, op.reg, 'r', err);
    op.reg.shift(o.top, o.left);
    P.ops.push_back(op);
  }
  PatternOp rd;
  rd.kind = PatternOp::READ;
  rd.r = o.top;
  rd.c = o.left;
  rd.lines = lines;
  P.ops.push_back(rd);
  for (const RegionSpec &rs : c.regions) {
    if (rs.kind != PatternOp::CLEAR) continue;
    PatternOp op;
    op.kind = rs.kind;
    std::string err;
    parseRegion(rs.text, op.reg, 'r', err);
    op.reg.shift(o.top, o.left);
    P.ops.push_back(op);
  }

  // Pattern-relative positions -> absolute ones
  if (c.symmFromSet) {
    long v = P.symm == VERTSYMM ? c.symmFrom + o.top : c.symmFrom + o.left;
    P.var[P.symm == VERTSYMM ? 115 : 114] = std::max(v, 1L);
  }
  for (Params::Push p : c.pushes) {   // measured from the trailing edge of the gen-0 changes
    long ref = LONG_MAX;
    for (int r = 0; r < (int)lines.size(); r++)
      for (int col = 0; col < (int)lines[r].size() && lines[r][col] != '!'; col++)
        if (strchr("0123", lines[r][col])) ref = std::min(ref, (long)p.dr * r + (long)p.dc * col);
    if (ref == LONG_MAX) ref = 0;
    p.k += p.den * ((long)p.dr * o.top + (long)p.dc * o.left + ref);
    P.pushes.push_back(p);
  }
  if (c.pushRight) P.var[104] += 3L * o.left;
  if (c.pushDown) P.var[105] += 3L * o.top;
  if (c.pushDownC2) P.var[109] += 2L * o.top;
  if (c.persistRegionSet) {
    Region r = c.persistRegion;
    r.shift(o.top, o.left);
    P.var[132] = r.minrow;
    P.var[133] = r.mincol;
    P.var[134] = r.maxrow;
    P.var[135] = r.maxcol;
  } else if (P.var[111]) {
    P.var[134] = P.HT;
    P.var[135] = P.WD;
  }
  P.checkBorder = !c.uncheckedBorder;
  if (!o.configPath.empty() && !o.noSave) {   // default results files, each unless given
    std::string base = o.configPath;
    if (base.size() > 4 && base.compare(base.size() - 4, 4, ".cfg") == 0) base.resize(base.size() - 4);
    if (o.jsonl.empty()) { o.jsonl = base + "-results.jsonl"; o.freshJsonl = true; }
    if (o.textOut.empty()) { o.textOut = base + "-results.txt"; o.freshText = true; }
  }
  if (P.maxgen < 1) fail("--max-gen must be at least 1");
  return true;
}

std::vector<std::string> cliSettings(const std::vector<std::string> &args) {
  static const char *KEEP[] = {"rule", "pattern", "clear", "no-change", "allow-change", "no-count",
                               "count", "no-check", "check", "must-reach"};
  std::vector<std::string> out;
  for (size_t i = 0; i < args.size(); i++) {
    const std::string &a = args[i];
    if (a.size() <= 2 || a.compare(0, 2, "--") != 0) {
      out.push_back("@config");
      continue;
    }
    std::string name = a.substr(2), value;
    size_t eq = name.find('=');
    if (eq != std::string::npos) {
      value = name.substr(eq + 1);
      name = name.substr(0, eq);
    } else {
      const Opt *opt = findOpt(name);
      if (opt && opt->arg && i + 1 < args.size()) value = args[++i];
    }
    for (const char *k : KEEP)
      if (name == k) {
        if (name == "pattern" && !value.empty() && value[0] != '/') {
          char real[PATH_MAX];
          if (realpath(value.c_str(), real)) value = real;
        }
        std::replace(value.begin(), value.end(), '\n', ' ');
        out.push_back(name + " = " + value);
      }
  }
  return out;
}

}  // namespace drift
