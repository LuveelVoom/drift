// dr2.c's command language: commands from the command line, then from the
// input until an empty line or end of file. Kept so old input files work
// unchanged (`drift --classic < old.in`).
#include "options.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <stdexcept>

namespace drift {

static void listcommands() {
  printf("Commands are:\n\n"
         "h#          Set max height of changed region\n"
         "w#          Set max width of changed region\n"
         "c#          Set max number of changed cells\n"
         "cc # # ...  Require these change counts in gens 0, 1, ...\n"
         "s#          Set random number seed\n"
         "P#          Set probability for free choices\n"
         "H#          Set height of space\n"
         "W#          Set width of space\n"
         "G#          Set max generation (dr2.c: fixed at 500)\n"
         "Rb###/s###  Set rule (INT and MAP rules also accepted)\n"
         "Kfile       Set known rotors file\n\n"
         "r# #        Read bkgd and curr\n"
         "C<region>   Clear bkgd and curr within region\n\n"
         "d0<region>  Disallow changes within region\n"
         "D0<region>  Allow changes within region\n"
         "d1<region>  Don't count changes within region\n"
         "D1<region>  Do count changes within region\n"
         "d2<region>  Don't check background stability within region\n\n"
         "skipstable  Don't print stable outcomes (except fizzles)\n"
         "nopics      Don't show patterns, just rotor descriptors\n"
         "skipfizzle  Don't print fizzle outcomes\n"
         "showfin     Show finished patterns\n"
         "showall     Show all generations\n\n"
         "nosymm, horsymm, vertsymm, diagsymm, rot90symm, rot180symm,\n"
         "plussymm, xsymm, fullsymm   Background symmetry\n\n"
         "v# #        Set variable\n"
         "?           Print this list\n"
         ";<text>     Comment\n\n");
}

static void ruleMessage(const Rule &rule) {
  printf("Rule set to %s\n", rule.canonical().c_str());
}

// Returns false at end of input.
static bool readline(std::istream &in, std::string &line) {
  if (!std::getline(in, line)) return false;
  if (!line.empty() && line.back() == '\r') line.pop_back();
  return true;
}

static void docommand(const std::string &cmdstr, bool cmdline, std::istream &in, Options &o) {
  const char *p = cmdstr.c_str();
  char cmd = *p;
  Params &P = o.params;
  std::string err;

  if (cmd == ';') printf("%s\n", p);
  else if (cmdstr == "?") listcommands();
  else if (cmdstr == "nosymm") P.symm = NOSYMM;
  else if (cmdstr == "horsymm") P.symm = HORSYMM;
  else if (cmdstr == "vertsymm") P.symm = VERTSYMM;
  else if (cmdstr == "diagsymm") P.symm = DIAGSYMM;
  else if (cmdstr == "rot90symm") P.symm = ROT90SYMM;
  else if (cmdstr == "rot180symm") P.symm = ROT180SYMM;
  else if (cmdstr == "plussymm") P.symm = PLUSSYMM;
  else if (cmdstr == "xsymm") P.symm = XSYMM;
  else if (cmdstr == "fullsymm") P.symm = FULLSYMM;
  else if (cmdstr == "skipstable") o.skipStable = true;
  else if (cmdstr == "nopics") o.noPics = true;
  else if (cmdstr == "skipfizzle") o.skipFizzle = true;
  else if (cmdstr == "showfin") o.showFin = true;
  else if (cmdstr == "showall") o.showAll = true;
  else if (cmd == 'c' && p[1] == 'c') {
    p += 2;
    P.reqchgcount.clear();
    while (*p == ' ') p++;
    while (*p) {
      P.reqchgcount.push_back(atoi(p));
      while (*p != ' ' && *p) p++;
      while (*p == ' ') p++;
    }
    printf("Initial change counts must be:");
    for (int v : P.reqchgcount) printf(" %d", v);
    printf("\n");
  } else if (cmd == 's') {
    P.seed = (unsigned int)atoi(p + 1);
    printf("Random seed = %d\n", atoi(p + 1));
  } else if (cmd == 'P') P.prob = atoi(p + 1);
  else if (cmd == 'h') P.maxheight = atoi(p + 1);
  else if (cmd == 'w') P.maxwidth = atoi(p + 1);
  else if (cmd == 'c') P.maxchng = atoi(p + 1);
  else if (cmd == 'G') P.maxgen = atoi(p + 1);
  else if (cmd == 'R') {
    if (!o.rule.parse(p + 1, err, true)) throw std::runtime_error("Bad rule: " + err);
    o.ruleSet = true;
    ruleMessage(o.rule);
  } else if (cmd == 'H' || cmd == 'W') {
    int v = atoi(p + 1);
    if (v < 5) throw std::runtime_error(cmd == 'H' ? "Bad height" : "Bad width");
    (cmd == 'H' ? P.HT : P.WD) = v;
    P.ops.clear();
    printf("%s changed, so universe cleared.\n", cmd == 'H' ? "Height" : "Width");
  } else if (cmd == 'K') o.knownRotorsFile = p + 1;
  else if (cmd == 'v') {
    int varnum;
    long varval;
    if (sscanf(p + 1, "%d %ld", &varnum, &varval) != 2 || varnum < 0 || varnum >= NUMVARS)
      throw std::runtime_error("Bad variable number");
    P.var[varnum] = varval;
    printf("var[%d] = %ld\n", varnum, varval);
  } else if (cmd == 'r' && !cmdline) {
    PatternOp op;
    op.kind = PatternOp::READ;
    if (sscanf(p + 1, "%d %d", &op.r, &op.c) != 2) throw std::runtime_error("Bad read command");
    std::string line;
    while (true) {
      if (!readline(in, line)) throw std::runtime_error("Bad character or EOF while reading");
      op.lines.push_back(line);
      if (line.find('!') != std::string::npos) break;
    }
    P.ops.push_back(op);
  } else if (cmd == 'C' || cmd == 'd' || cmd == 'D') {
    PatternOp op;
    if (cmd != 'C') {
      op.bit = p[1] - '0';
      if (op.bit < 0 || op.bit > 7) throw std::runtime_error("Bad bit in 'd' or 'D' command.");
      printf(cmd == 'd' ? "Setting flag %d in region\n" : "Clearing flag %d in region\n", op.bit);
      p++;
    }
    op.kind = cmd == 'C' ? PatternOp::CLEAR : cmd == 'd' ? PatternOp::SETFLAG : PatternOp::CLEARFLAG;
    if (!parseRegion(p + 1, op.reg, 'r', err)) throw std::runtime_error(err);
    printf("Region type %c.  Rows %d to %d.  Cols %d to %d.\n", op.reg.type,
           std::max(op.reg.minrow, 0), std::min(op.reg.maxrow, P.HT - 1),
           std::max(op.reg.mincol, 0), std::min(op.reg.maxcol, P.WD - 1));
    P.ops.push_back(op);
  } else
    throw std::runtime_error("Unknown command: " + cmdstr);
}

void readClassic(const std::vector<std::string> &args, std::istream &in, Options &o) {
  if (!o.ruleSet) {
    std::string err;
    o.rule.parse("B3/S23", err);
  }
  ruleMessage(o.rule);
  if (args.empty()) printf("Type '?' for list of commands\n\n");
  for (const std::string &a : args) docommand(a, true, in, o);
  std::string line;
  while (readline(in, line) && !line.empty()) docommand(line, false, in, o);
}

}  // namespace drift
