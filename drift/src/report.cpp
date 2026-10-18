#include "report.h"

#include <cstdarg>
#include <stdexcept>
#include <vector>

namespace drift {

static std::string fmt(const char *f, ...) __attribute__((format(printf, 1, 2)));
static std::string fmt(const char *f, ...) {
  char buf[1024];
  va_list ap;
  va_start(ap, f);
  vsnprintf(buf, sizeof buf, f, ap);
  va_end(ap);
  return buf;
}

static std::string jsonStr(const std::string &s) {
  std::string out = "\"";
  for (char ch : s) {
    if (ch == '"' || ch == '\\') out += '\\', out += ch;
    else if (ch == '\n') out += "\\n";
    else if (ch == '\t') out += "\\t";
    else if ((unsigned char)ch < 32) out += fmt("\\u%04x", ch);
    else out += ch;
  }
  return out + "\"";
}

// Run-length encode rows of state characters ('.' or 'b' = empty).
static std::string rle(const std::vector<std::string> &rows, char empty) {
  std::string out, line;
  auto emit = [&](long n, char ch) {
    std::string tok = (n > 1 ? std::to_string(n) : "") + ch;
    if (line.size() + tok.size() > 70) { out += line + "\n"; line.clear(); }
    line += tok;
  };
  long pendingRows = 0;
  for (size_t r = 0; r < rows.size(); r++) {
    const std::string &row = rows[r];
    size_t end = row.size();
    while (end > 0 && row[end - 1] == empty) end--;
    if (end == 0) { pendingRows++; continue; }
    if (r > 0) emit(pendingRows + 1, '$');
    pendingRows = 0;
    for (size_t c = 0; c < end;) {
      size_t c2 = c;
      while (c2 < end && row[c2] == row[c]) c2++;
      emit((long)(c2 - c), row[c]);
      c = c2;
    }
  }
  emit(1, '!');
  return out + line + "\n";
}

Reporter::Reporter(const Options &opt, const KnownRotors *k, size_t n)
    : o(opt), nknown(n) {
  (void)k;
  if (!o.jsonl.empty()) {
    json = fopen(o.jsonl.c_str(), "a");
    if (!json) throw std::runtime_error("can't open '" + o.jsonl + "' for writing");
  }
}

Reporter::~Reporter() {
  if (json) fclose(json);
}

// Picture of bkgd + gen g (dr2.c's characters) in the same bounding box as
// dr2.c's display(), plus LifeHistory and two-state RLE cropped to the known
// cells and to the live cells respectively.
std::string Reporter::picture(const Search &s, int g, std::string *lifehistory,
                              std::string *plain) const {
  int HT = s.HT, WD = s.WD;
  int minr = HT, maxr = -1, minc = WD, maxc = -1;
  for (int r = 2; r < HT - 2; r++)
    for (int c = 2; c < WD - 2; c++)
      if (s.bkgd[s.idx(r, c)] == ON) {
        minr = std::min(minr, r); maxr = std::max(maxr, r);
        minc = std::min(minc, c); maxc = std::max(maxc, c);
      }
  std::vector<char> changed((size_t)(HT + 4) * s.stride(), 0);
  for (int q = s.chgd[g]; q < s.nays[g]; q++) {
    const Search::Pt &p = s.chglist[q];
    changed[s.idx(p.r, p.c)] = 1;
    minr = std::min(minr, p.r); maxr = std::max(maxr, p.r);
    minc = std::min(minc, p.c); maxc = std::max(maxc, p.c);
  }
  if (maxr < 0) { minr = maxr = HT / 2; minc = maxc = WD / 2; }
  minr = std::max(minr - 2, 0); maxr = std::min(maxr + 2, HT - 1);
  minc = std::max(minc - 2, 0); maxc = std::min(maxc + 2, WD - 1);

  std::string pic = fmt("gen %d, rows %d..%d, cols %d..%d\n", g, minr - o.top, maxr - o.top,
                        minc - o.left, maxc - o.left);
  for (int r = minr; r <= maxr; r++) {
    std::string line;
    for (int c = minc; c <= maxc; c++) {
      int i = s.idx(r, c);
      uint8_t b = s.bkgd[i];
      line += b == OFF ? (changed[i] ? '1' : '.') : b == ON ? (changed[i] ? '0' : 'o') : ',';
    }
    while (line.size() > 1 && line.back() == ',') line.pop_back();
    pic += line + "\n";
  }

  // RLE: LifeHistory of all known cells (inside the space's fixed border),
  // and gen g alone as a two-state pattern.
  auto crop = [&](auto keep, int &r0, int &r1, int &c0, int &c1) {
    r0 = HT; r1 = -1; c0 = WD; c1 = -1;
    for (int r = 2; r < HT - 2; r++)
      for (int c = 2; c < WD - 2; c++)
        if (keep(s.idx(r, c))) {
          r0 = std::min(r0, r); r1 = std::max(r1, r);
          c0 = std::min(c0, c); c1 = std::max(c1, c);
        }
  };
  int r0, r1, c0, c1;
  if (lifehistory) {
    crop([&](int i) { return s.bkgd[i] != UNK; }, r0, r1, c0, c1);
    std::vector<std::string> rows;
    for (int r = r0; r <= r1; r++) {
      std::string row;
      for (int c = c0; c <= c1; c++) {
        int i = s.idx(r, c);
        uint8_t b = s.bkgd[i];
        row += b == UNK ? '.' : b == ON ? (changed[i] ? 'D' : 'A') : (changed[i] ? 'C' : 'B');
      }
      rows.push_back(row);
    }
    *lifehistory = r1 < 0 ? "x = 0, y = 0, rule = LifeHistory\n!\n"
                          : fmt("x = %d, y = %d, rule = LifeHistory\n", c1 - c0 + 1, r1 - r0 + 1) +
                                rle(rows, '.');
  }
  if (plain) {
    auto live = [&](int i) { return s.bkgd[i] != UNK && (s.bkgd[i] == ON) != (changed[i] != 0); };
    crop(live, r0, r1, c0, c1);
    std::vector<std::string> rows;
    for (int r = r0; r <= r1; r++) {
      std::string row;
      for (int c = c0; c <= c1; c++) row += live(s.idx(r, c)) ? 'o' : 'b';
      rows.push_back(row);
    }
    std::string rule = o.rule.canonical();
    *plain = r1 < 0 ? fmt("x = 0, y = 0, rule = %s\n!\n", rule.c_str())
                    : fmt("x = %d, y = %d, rule = %s\n", c1 - c0 + 1, r1 - r0 + 1, rule.c_str()) +
                          rle(rows, 'b');
  }
  return pic;
}

void Reporter::outcome(Search &s, Outcome oc, int per, bool semifzl, uint64_t h) {
  counts[oc]++;
  if (o.classic) classic(s, oc, per, semifzl, h);
  else modern(s, oc, per, semifzl);
  fflush(stdout);
}

// Exactly what dr2.c's main() prints for each outcome.
void Reporter::classic(Search &s, Outcome oc, int per, bool semifzl, uint64_t h) {
  const long *var = s.P.var;
  int gen = s.gen;
  auto display = [&](int g) {
    if (o.noPics) printf("\n");
    else fputs(s.display(g).c_str(), stdout);
  };
  auto showRest = [&](bool fin) {
    if (fin && o.showFin) display(gen);
    if (o.showAll)
      for (int g = 1; g <= gen; g++) display(g);
  };
  switch (oc) {
    case PERIODIC:
      if (var[131] && per == 3) forget(h);
      else {
        printf("*****  Period %d at gen %d%s\n", per, gen - per, semifzl ? " (semifizzle)" : "");
        fputs(s.oscinfo(per, 'p').line.c_str(), stdout);
        fputs(s.oscinfo(gen, 'u').line.c_str(), stdout);
        fputs(s.dispchgcts(gen).c_str(), stdout);
        printed++;
      }
      if (!var[131] || per > 6) display(0);
      showRest(true);
      break;
    case STABLE:
      if (o.skipStable) return;
      printf("*****  Stable at gen %d%s\n", gen - 1, semifzl ? " (semifizzle)" : "");
      fputs(s.oscinfo(gen, 's').line.c_str(), stdout);
      fputs(s.dispchgcts(gen).c_str(), stdout);
      display(0);
      showRest(true);
      printed++;
      break;
    case FIZZLE:
      if (o.skipFizzle) return;
      printf("*****  Fizzle at gen %d\n", gen);
      fputs(s.oscinfo(gen, 'f').line.c_str(), stdout);
      fputs(s.dispchgcts(gen).c_str(), stdout);
      display(0);
      showRest(false);
      printed++;
      break;
    case MAXGEN:
      printf("*****  Max gen (%d) reached\n", s.P.maxgen);
      fputs(s.dispchgcts(gen).c_str(), stdout);
      display(0);
      showRest(true);
      printed++;
      break;
  }
}

static std::string countLines(const Search &s, int gen) {
  auto row = [&](const char *label, auto value) {
    std::string out = label;
    for (int g = 0; g <= gen; g++) out += (g && g % 5 == 0 ? "  " : " ") + value(g);
    return out + "\n";
  };
  std::string out;
  bool different = false;
  for (int g = 0; g <= gen; g++) different |= s.numchanged(g) != s.chgcount[g];
  if (different) out += row("all changes:", [&](int g) { return std::to_string(s.numchanged(g)); });
  out += row("changes:", [&](int g) { return std::to_string(s.chgcount[g]); });
  out += row("sizes:  ", [&](int g) { return fmt("%dx%d", s.height[g], s.width[g]); });
  if (s.P.var[129]) out += row("age sums:", [&](int g) { return std::to_string(s.agesm[g]); });
  return out;
}

void Reporter::modern(Search &s, Outcome oc, int per, bool semifzl) {
  const long *var = s.P.var;
  int gen = s.gen;
  OscInfo main, hist;
  std::string kind, title;
  switch (oc) {
    case PERIODIC:
      if (o.skipPeriodic || per < o.minPeriod) return;
      if (var[131] && per <= 6) return;
      main = s.oscinfo(per, 'p');
      hist = s.oscinfo(gen, 'u');
      if (!main.known) unknownOsc++;
      if (o.skipKnown && main.known) return;
      kind = "oscillator";
      title = fmt("p%d from gen %d", per, gen - per);
      break;
    case STABLE:
      if (o.skipStable) return;
      main = s.oscinfo(gen, 's');
      if (o.skipKnown && main.known) return;
      kind = "stable";
      title = fmt("from gen %d", gen - 1);
      break;
    case FIZZLE:
      if (o.skipFizzle) return;
      main = s.oscinfo(gen, 'f');
      if (o.skipKnown && main.known) return;
      kind = "fizzle";
      title = fmt("at gen %d", gen);
      break;
    case MAXGEN:
      if (o.skipMaxgen) return;
      kind = "max gen";
      title = fmt("still going at gen %d: possible moving signal", gen);
      break;
  }
  printed++;
  if (semifzl && (oc == PERIODIC || oc == STABLE)) title += " (semifizzle)";

  std::string name;
  if (oc != MAXGEN) {
    if (main.known) name = main.name;
    else if (oc == PERIODIC) name = "NEW ROTOR";
    if (main.gap) name += (name.empty() ? "" : ", ") + fmt("split rotor, gap %d", main.gap);
  }
  std::string out = fmt("***** #%ld %s %s", printed, kind.c_str(), title.c_str());
  if (!name.empty()) out += ": " + name;
  out += "\n";
  if (oc == PERIODIC) out += "rotor:   " + main.desc + "\n";
  if (oc == PERIODIC) out += "history: " + hist.desc + (hist.known ? "  (" + hist.name + ")" : "") + "\n";
  else if (oc != MAXGEN) out += "history: " + main.desc + "\n";
  out += countLines(s, gen);
  std::string lh, plain;
  std::string pic = picture(s, 0, &lh, &plain);
  if (!o.noPics) out += pic;
  if (!o.noRle) out += lh;
  if ((o.showFin && oc != FIZZLE) || oc == MAXGEN) {
    std::string lh2;
    std::string pic2 = picture(s, gen, &lh2, nullptr);
    if (!o.noPics) out += pic2;
    if (!o.noRle && oc == MAXGEN) out += lh2;
  }
  if (o.showAll)
    for (int g = 1; g <= gen; g++) out += picture(s, g, nullptr, nullptr);
  out += "\n";
  fputs(out.c_str(), stdout);

  if (json) {
    std::string cc, sz;
    for (int g = 0; g <= gen; g++) {
      cc += (g ? "," : "") + std::to_string(s.chgcount[g]);
      sz += std::string(g ? "," : "") + "\"" + fmt("%dx%d", s.height[g], s.width[g]) + "\"";
    }
    std::string j = fmt("{\"n\":%ld,\"kind\":\"%s\",\"gen\":%d", printed,
                        oc == MAXGEN ? "maxgen" : kind.c_str(), gen);
    if (oc == PERIODIC) j += fmt(",\"period\":%d", per);
    if (oc == PERIODIC || oc == STABLE) j += semifzl ? ",\"semifizzle\":true" : ",\"semifizzle\":false";
    if (oc != MAXGEN) {
      j += std::string(oc == PERIODIC ? ",\"rotor\":" : ",\"history\":") + jsonStr(main.desc);
      j += std::string(",\"known\":") + (main.known ? "true" : "false");
      if (main.known) j += ",\"name\":" + jsonStr(main.name);
      if (main.gap) j += fmt(",\"gap\":%d", main.gap);
    }
    if (oc == PERIODIC) j += ",\"history\":" + jsonStr(hist.desc);
    j += ",\"change_counts\":[" + cc + "],\"sizes\":[" + sz + "]";
    j += ",\"rule\":" + jsonStr(o.rule.canonical());
    j += ",\"lifehistory\":" + jsonStr(lh) + ",\"gen0\":" + jsonStr(plain) + "}\n";
    fputs(j.c_str(), json);
    fflush(json);
  }
}

void Reporter::newMaxGen(Search &s) {
  if (s.gen <= maxgen) return;
  maxgen = s.gen;
  if (!o.classic) return;
  printf("maxgenreached = %d\n", s.gen);
  fputs(s.dispchgcts(s.gen - 1).c_str(), stdout);
  if (o.noPics) printf("\n");
  else fputs(s.display(0).c_str(), stdout);
  fflush(stdout);
}

void Reporter::tick(Search &s) {
  if (!o.classic) return;
  printf("computecellorbackup calls: %ld 000000\n", s.counthi);
  fputs(s.display(0).c_str(), stdout);
  fputs(s.dispchgcts(s.gen - 1).c_str(), stdout);
  fflush(stdout);
}

void Reporter::note(Search &, const std::string &msg) {
  if (o.classic) fputs(msg.c_str(), stdout);
}

static const char *SYMM_NAMES[] = {"none", "hor", "diag", "rot90", "rot180",
                                   "plus", "x", "full", "vert"};

void Reporter::header(const Search &base, int threads) {
  const Params &P = base.P;
  if (o.classic) {
    printf("Reading file '%s'\n", o.knownRotorsFile.c_str());
    printf("%zu known rotors read\n\n", nknown);
    printf("Max height of changed region = %d\n", P.maxheight);
    printf("Max width of changed region = %d\n", P.maxwidth);
    printf("Max number of changed cells = %d\n", P.maxchng);
    printf("Probability = %d\n", P.prob);
    if (o.skipStable) printf("Skipping stable outcomes\n");
    if (o.noPics) printf("Not showing pictures\n");
    if (o.skipFizzle) printf("Skipping fizzle outcomes\n");
    if (o.showFin) printf("Showing finished patterns\n");
    if (o.showAll) printf("Showing all gens\n");
    printf("Height = %d\nWidth = %d\n", P.HT, P.WD);
    static const char *names[] = {nullptr, "Horizontal symmetry", "Diagonal symmetry",
                                  "90 degree rotational symmetry", "180 degree rotational symmetry",
                                  "Horizontal & vertical symmetry", "Symmetry across both diagonals",
                                  "Full symmetry", "Vertical symmetry"};
    if (P.symm != NOSYMM) printf("%s\n", names[P.symm]);
    fputs(base.display(0).c_str(), stdout);
    printf("Beginning search\n");
    fflush(stdout);
    return;
  }
  printf("drift: rule %s, space %dx%d, at most %d changed cells in %dx%d (w x h), max gen %d\n",
         o.rule.canonical().c_str(), P.HT, P.WD, P.maxchng, P.maxwidth, P.maxheight, P.maxgen);
  printf("symmetry %s, seed %lu, %d thread%s, known rotors: %zu%s\n", SYMM_NAMES[P.symm], P.seed,
         threads, threads == 1 ? "" : "s", nknown,
         nknown ? (" (" + o.knownRotorsFile + ")").c_str() : "");
  for (const std::string &w : o.warnings) printf("warning: %s\n", w.c_str());
  printf("legend: o on  . off  , unknown  1 on in gen 0 only  0 off in gen 0 only\n");
  printf("starting position (rows/cols relative to the pattern's top-left):\n");
  std::string lh;
  Search &b = const_cast<Search &>(base);
  fputs(picture(b, 0, &lh, nullptr).c_str(), stdout);
  printf("\n");
  fflush(stdout);
}

void Reporter::footer(double seconds, long long steps, bool finished, bool resumed) {
  if (o.classic) {
    if (finished) printf("No more objects\n");
    fflush(stdout);
    return;
  }
  printf("%s after %.1fs%s, %lld steps (%.2fM/s).\n",
         finished ? "Search complete" : "Search stopped", seconds,
         resumed ? " (this session)" : "", steps, seconds > 0 ? steps / seconds / 1e6 : 0.0);
  printf("Found %ld oscillators (%ld with unknown rotors), %ld stable, %ld fizzles, %ld max gen; "
         "printed %ld. Highest generation reached: %d.\n",
         counts[PERIODIC], unknownOsc, counts[STABLE], counts[FIZZLE], counts[MAXGEN], printed,
         maxgen);
  fflush(stdout);
}

}  // namespace drift
