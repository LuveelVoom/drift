// drift: command line front end, worker threads, progress and checkpoints.
//
// Parallelism: the search tree is split on decision paths. Every worker runs
// its own copy of the search from a path (replaying the recorded choices,
// which may not be undone) and explores the subtree below it. When a worker is
// idle, a busy one donates the untried branch of its shallowest free choice.
// A checkpoint is the list of unexplored paths, collected while all workers
// are paused.
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <climits>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <deque>
#include <fstream>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <thread>

#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

#include "options.h"
#include "report.h"
#include "search.h"

using namespace drift;

namespace {

std::atomic<int> gSignal{0};
void onSignal(int) {
  if (++gSignal >= 2) _exit(130);
}

using Clock = std::chrono::steady_clock;
double secondsSince(Clock::time_point t) {
  return std::chrono::duration<double>(Clock::now() - t).count();
}

struct Item {
  std::vector<uint8_t> path;
  double w;
};

// True if these live cells, alone in empty space, are a spaceship: they come
// back moved within 40 gens. A spaceship spark is meant to fly in from empty
// space, so it needn't touch unknown cells.
bool isSpaceship(const Rule &rule, std::vector<std::pair<int, int>> live) {
  auto norm = [](std::vector<std::pair<int, int>> v, int &r0, int &c0) {
    std::sort(v.begin(), v.end());
    r0 = INT_MAX, c0 = INT_MAX;
    for (auto &p : v) r0 = std::min(r0, p.first), c0 = std::min(c0, p.second);
    for (auto &p : v) p.first -= r0, p.second -= c0;
    return v;
  };
  std::sort(live.begin(), live.end());
  int R0, C0;
  auto start = norm(live, R0, C0);
  for (int g = 1; g <= 40 && !live.empty() && live.size() < 200; g++) {
    std::vector<std::pair<int, int>> cand, next;
    for (auto &p : live)
      for (int k = 0; k < 9; k++) cand.push_back({p.first + DR[k], p.second + DC[k]});
    std::sort(cand.begin(), cand.end());
    cand.erase(std::unique(cand.begin(), cand.end()), cand.end());
    for (auto &p : cand) {
      int code = 0;
      for (int k = 0; k < 9; k++)
        if (std::binary_search(live.begin(), live.end(), std::make_pair(p.first + DR[k], p.second + DC[k])))
          code += POW3[k];
      if (rule.next3[code] == ON) next.push_back(p);
    }
    live = next;
    int r0, c0;
    if (norm(live, r0, c0) == start && (r0 != R0 || c0 != C0)) return true;
  }
  return false;
}

uint64_t fnv(uint64_t h, const void *data, size_t n) {
  const unsigned char *p = (const unsigned char *)data;
  for (size_t i = 0; i < n; i++) h = (h ^ p[i]) * 1099511628211ULL;
  return h;
}
uint64_t fnvStr(uint64_t h, const std::string &s) {
  uint64_t n = s.size();
  return fnv(fnv(h, &n, sizeof n), s.data(), s.size());
}

// Everything that changes which subtrees exist. A checkpoint may only be
// resumed with the same fingerprint.
uint64_t fingerprint(const Options &o) {
  const Params &P = o.params;
  uint64_t h = 1469598103934665603ULL;
  h = fnvStr(h, o.rule.canonical());
  long nums[] = {P.HT, P.WD, P.maxgen, P.maxchng, P.maxwidth, P.maxheight, P.prob,
                 (long)P.seed, P.symm, P.checkBorder};
  h = fnv(h, nums, sizeof nums);
  h = fnv(h, P.var, sizeof P.var);
  if (P.escape) h = fnvStr(h, "escape");
  for (int v : P.reqchgcount) h = fnv(h, &v, sizeof v);
  for (const Params::Push &p : P.pushes) {
    long f[] = {p.dr, p.dc, p.num, p.den, p.k};
    h = fnv(h, f, sizeof f);
  }
  for (const PatternOp &op : P.ops) {
    long f[] = {op.kind, op.r, op.c, op.bit, op.reg.type, op.reg.r0, op.reg.c0, op.reg.r1,
                op.reg.c1, op.reg.r2, op.reg.c2};
    h = fnv(h, f, sizeof f);
    for (const std::string &l : op.lines) h = fnvStr(h, l);
  }
  return h;
}

uint64_t splitmix(uint64_t x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

std::string hms(double s) {
  char buf[64];
  long t = (long)s;
  if (t >= 86400) snprintf(buf, sizeof buf, "%ldd%02ldh", t / 86400, t % 86400 / 3600);
  else if (t >= 3600) snprintf(buf, sizeof buf, "%ldh%02ldm", t / 3600, t % 3600 / 60);
  else if (t >= 60) snprintf(buf, sizeof buf, "%ldm%02lds", t / 60, t % 60);
  else snprintf(buf, sizeof buf, "%lds", t);
  return buf;
}

struct Saved {   // what a checkpoint holds besides the options
  std::vector<std::string> args;
  uint64_t fp = 0;
  double elapsed = 0;
  long long steps = 0;
  long printed = 0, unknownOsc = 0, counts[4] = {0, 0, 0, 0};
  int maxgen = 0;
  std::vector<uint64_t> hashes;
  std::vector<Item> items;
};

std::string escapeArg(const std::string &a) {
  std::string out;
  for (char ch : a) {
    if (ch == '\\') out += "\\\\";
    else if (ch == '\n') out += "\\n";
    else out += ch;
  }
  return out;
}
std::string unescapeArg(const std::string &a) {
  std::string out;
  for (size_t i = 0; i < a.size(); i++) {
    if (a[i] == '\\' && i + 1 < a.size()) {
      i++;
      out += a[i] == 'n' ? '\n' : a[i];
    } else
      out += a[i];
  }
  return out;
}

void writeCheckpoint(const std::string &path, const Saved &s) {
  std::string tmp = path + ".tmp";
  FILE *f = fopen(tmp.c_str(), "w");
  if (!f) throw std::runtime_error("can't write checkpoint '" + tmp + "'");
  fprintf(f, "drift-checkpoint 1\nfingerprint %016llx\n", (unsigned long long)s.fp);
  fprintf(f, "args %zu\n", s.args.size());
  for (const std::string &a : s.args) fprintf(f, "%s\n", escapeArg(a).c_str());
  fprintf(f, "elapsed %.3f\nsteps %lld\nprinted %ld\nunknown %ld\nmaxgen %d\n", s.elapsed, s.steps,
          s.printed, s.unknownOsc, s.maxgen);
  fprintf(f, "counts %ld %ld %ld %ld\n", s.counts[0], s.counts[1], s.counts[2], s.counts[3]);
  fprintf(f, "hashes %zu\n", s.hashes.size());
  for (uint64_t h : s.hashes) fprintf(f, "%016llx\n", (unsigned long long)h);
  fprintf(f, "items %zu\n", s.items.size());
  for (const Item &it : s.items) {
    fprintf(f, "%.17g ", it.w);
    for (uint8_t b : it.path) fputc('0' + b, f);
    fputc('\n', f);
  }
  fprintf(f, "end\n");
  if (fclose(f) != 0 || rename(tmp.c_str(), path.c_str()) != 0)
    throw std::runtime_error("can't write checkpoint '" + path + "'");
}

Saved readCheckpoint(const std::string &path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("can't open checkpoint '" + path + "'");
  Saved s;
  std::string word, line;
  auto bad = [&]() { return std::runtime_error("'" + path + "' is not a valid drift checkpoint"); };
  auto expect = [&](const char *w) {
    if (!(in >> word) || word != w) throw bad();
  };
  expect("drift-checkpoint");
  int version;
  in >> version;
  expect("fingerprint");
  std::string hex;
  in >> hex;
  s.fp = strtoull(hex.c_str(), nullptr, 16);
  expect("args");
  size_t n;
  in >> n;
  std::getline(in, line);
  for (size_t i = 0; i < n; i++) {
    std::getline(in, line);
    s.args.push_back(unescapeArg(line));
  }
  expect("elapsed"); in >> s.elapsed;
  expect("steps"); in >> s.steps;
  expect("printed"); in >> s.printed;
  expect("unknown"); in >> s.unknownOsc;
  expect("maxgen"); in >> s.maxgen;
  expect("counts"); in >> s.counts[0] >> s.counts[1] >> s.counts[2] >> s.counts[3];
  expect("hashes"); in >> n;
  for (size_t i = 0; i < n; i++) {
    in >> hex;
    s.hashes.push_back(strtoull(hex.c_str(), nullptr, 16));
  }
  expect("items"); in >> n;
  std::getline(in, line);
  for (size_t i = 0; i < n; i++) {
    std::getline(in, line);
    std::istringstream ls(line);
    Item it;
    std::string bits;
    ls >> it.w >> bits;
    for (char ch : bits) it.path.push_back(ch == '1');
    s.items.push_back(it);
  }
  expect("end");
  return s;
}

class Coordinator : public Sink {
 public:
  Coordinator(Reporter &r, const Search &b, const Options &opt, int n, int active)
      : rep(r), base(b), o(opt), nthreads(n), workers(n), limit(active) {
    ttyProgress = !o.quiet && isatty(2);
  }

  // --- Sink: results go to the reporter one at a time
  bool hashnew(uint64_t h) override {
    std::lock_guard<std::mutex> l(repMu);
    return rep.hashnew(h);
  }
  void forget(uint64_t h) override {
    std::lock_guard<std::mutex> l(repMu);
    rep.forget(h);
  }
  void outcome(Search &s, Outcome oc, int per, bool semifzl, uint64_t h) override {
    std::lock_guard<std::mutex> l(repMu);
    clearProgressLine();
    rep.outcome(s, oc, per, semifzl, h);
  }
  void newMaxGen(Search &s) override {
    if (s.gen <= maxgenSeen.load(std::memory_order_relaxed)) return;
    std::lock_guard<std::mutex> l(repMu);
    clearProgressLine();
    rep.newMaxGen(s);
    maxgenSeen = rep.maxgen;
  }
  void tick(Search &s) override {
    if (!o.classic) return;
    std::lock_guard<std::mutex> l(repMu);
    rep.tick(s);
  }
  void note(Search &s, const std::string &msg) override {
    if (!o.classic) return;
    std::lock_guard<std::mutex> l(repMu);
    rep.note(s, msg);
  }

  bool poll(Search &s) override {
    Worker &w = workers[tid];
    w.steps.store(w.doneSteps + s.steps, std::memory_order_relaxed);
    if (o.maxSteps && totalSteps() >= o.maxSteps) {
      if (o.checkpoint.empty()) stopReq = true;
      else limitHit = true;   // the monitor saves the rest, then stops
    }
    if (tid >= limit.load(std::memory_order_relaxed) && !pauseReq.load()) {
      // This thread has been switched off: hand all its remaining work back.
      std::lock_guard<std::mutex> l(qMu);
      std::vector<std::pair<std::vector<uint8_t>, double>> pend;
      s.pending(pend);
      for (auto &p : pend) {
        w.handedBack += p.second;
        queue.push_back({std::move(p.first), p.second});
      }
      w.yielded = true;
      qCv.notify_all();
      return true;
    }
    if ((++w.polls & 15) == 0) w.progress.store(s.progress(), std::memory_order_relaxed);
    if (wantWork.load(std::memory_order_relaxed)) {
      std::lock_guard<std::mutex> l(qMu);
      if ((int)queue.size() < idleOn()) {
        Item it;
        if (s.donate(it.path, it.w)) {
          queue.push_back(std::move(it));
          qCv.notify_all();
        }
      }
      if ((int)queue.size() >= idleOn()) wantWork = false;
    }
    if (pauseReq.load()) {
      std::unique_lock<std::mutex> l(qMu);
      std::vector<std::pair<std::vector<uint8_t>, double>> pend;
      s.pending(pend);
      for (auto &p : pend) snapshot.push_back({std::move(p.first), p.second});
      paused++;
      monCv.notify_all();
      qCv.wait(l, [&] { return !pauseReq.load(); });
      paused--;
    }
    return stopReq.load();
  }

  // Runs everything; returns true if the whole search finished.
  bool run(std::vector<Item> items, Saved &saved, const std::vector<std::string> &args) {
    for (Item &it : items) {
      todo += it.w;
      queue.push_back(std::move(it));
    }
    completed = 1.0 - todo;
    elapsed0 = saved.elapsed;
    steps0 = saved.steps;
    t0 = Clock::now();
    std::vector<std::thread> ts;
    for (int i = 0; i < nthreads; i++) ts.emplace_back([this, i] { worker(i); });

    auto lastCkpt = Clock::now(), lastProg = Clock::now(), lastThreads = Clock::now();
    bool interrupted = false;
    while (true) {
      {
        std::unique_lock<std::mutex> l(qMu);
        monCv.wait_for(l, std::chrono::milliseconds(200), [&] { return exited == nthreads; });
        if (exited == nthreads) break;
      }
      if (!o.threadsFile.empty() && secondsSince(lastThreads) >= 1) {
        readThreadsFile();
        lastThreads = Clock::now();
      }
      if (limitHit.load() || (o.maxTime > 0 && sessionSeconds() >= o.maxTime)) {
        if (!o.checkpoint.empty()) checkpoint(saved, args);
        stopReq = true;
        stop();
        break;
      }
      if (gSignal.load()) {
        interrupted = true;
        if (!o.checkpoint.empty()) checkpoint(saved, args);
        stop();
        break;
      }
      if (!o.checkpoint.empty() && secondsSince(lastCkpt) >= o.checkpointEvery) {
        checkpoint(saved, args);
        lastCkpt = Clock::now();
      }
      if (!o.quiet && secondsSince(lastProg) >= o.progressEvery) {
        progressLine();
        lastProg = Clock::now();
      }
    }
    for (auto &t : ts) t.join();
    {
      std::lock_guard<std::mutex> l(repMu);
      clearProgressLine();
    }
    finished = !interrupted && !stopReq && queue.empty();
    if (!o.checkpoint.empty() && finished) {   // record that nothing is left
      queue.clear();
      snapshot.clear();
      writeState(saved, args);
    }
    if (!interrupted && !finished && !o.checkpoint.empty())
      fprintf(stderr, "\nStopped at the limit. Continue with: drift --resume %s\n", o.checkpoint.c_str());
    if (interrupted)
      fprintf(stderr, "\nInterrupted.%s\n",
              o.checkpoint.empty() ? "" : (" Resume with: drift --resume " + o.checkpoint).c_str());
    return finished;
  }

  long long totalSteps() const {
    long long t = 0;
    for (const Worker &w : workers) t += w.steps.load();
    return t;
  }
  double sessionSeconds() const { return secondsSince(t0); }
  long lastHi = 0, lastLo = 0;   // dr2.c's call counter of the last search

 private:
  struct Worker {
    std::atomic<long long> steps{0};
    std::atomic<double> progress{0};
    long long doneSteps = 0;
    unsigned polls = 0;
    bool yielded = false;    // stopped because the thread limit was lowered
    double handedBack = 0;   // weight of the work it put back on the queue
  };
  static thread_local int tid;

  Reporter &rep;
  const Search &base;
  const Options &o;
  int nthreads;
  std::vector<Worker> workers;

  std::mutex repMu, qMu;
  std::condition_variable qCv, monCv;
  std::deque<Item> queue;
  std::vector<Item> snapshot;
  int idle = 0, paused = 0, exited = 0;
  double todo = 0, completed = 0;
  std::atomic<bool> wantWork{false}, pauseReq{false}, stopReq{false}, limitHit{false};
  std::atomic<int> limit;   // threads with id >= limit sit out (--threads-file)
  std::atomic<int> maxgenSeen{0};
  bool done = false, finished = false, ttyProgress = false, progressShown = false;
  Clock::time_point t0;
  double elapsed0 = 0;
  long long steps0 = 0;

  void worker(int id) {
    tid = id;
    Worker &w = workers[id];
    while (true) {
      Item it;
      {
        std::unique_lock<std::mutex> l(qMu);
        idle++;
        while (true) {
          if (stopReq || done) {
            exited++;
            monCv.notify_all();
            return;
          }
          if (pauseReq) {
            paused++;
            monCv.notify_all();
            qCv.wait(l, [&] { return !pauseReq.load(); });
            paused--;
            continue;
          }
          bool on = id < limit.load();
          if (on && !queue.empty()) break;
          if (idle == nthreads && queue.empty()) {   // nobody has work left: the search is over
            done = true;
            qCv.notify_all();
            continue;
          }
          if (on) wantWork = true;
          qCv.wait(l);
        }
        it = std::move(queue.front());
        queue.pop_front();
        idle--;
        if ((int)queue.size() < idleOn()) wantWork = true;
      }
      Search s = base;
      s.prefix = it.path;
      s.weight = it.w;
      if (!it.path.empty()) {
        uint64_t h = 1469598103934665603ULL;
        h = fnv(h, it.path.data(), it.path.size());
        s.seed(splitmix(h ^ base.P.seed));
      }
      bool fin = s.run(*this);
      std::lock_guard<std::mutex> l(qMu);
      w.doneSteps += s.steps;
      w.steps.store(w.doneSteps);
      w.progress.store(0);
      lastHi = s.counthi;
      lastLo = s.countlo;
      if (w.yielded) {   // its work is back on the queue; wait to be switched on again
        completed += it.w - s.donatedWeight - w.handedBack;
        w.yielded = false;
        w.handedBack = 0;
        continue;
      }
      if (!fin) {
        exited++;
        monCv.notify_all();
        return;
      }
      completed += it.w - s.donatedWeight;
    }
  }

  // Pause every worker, then collect the queue and the workers' pending paths.
  void pauseAll() {
    std::unique_lock<std::mutex> l(qMu);
    snapshot.clear();
    pauseReq = true;
    qCv.notify_all();
    monCv.wait(l, [&] { return paused + exited >= nthreads; });
  }
  void resumeAll() {
    std::lock_guard<std::mutex> l(qMu);
    pauseReq = false;
    qCv.notify_all();
  }
  // Idle threads that are switched on (switched-off ones are always idle).
  int idleOn() const { return idle - (nthreads - limit.load(std::memory_order_relaxed)); }

  void readThreadsFile() {
    FILE *f = fopen(o.threadsFile.c_str(), "r");
    if (!f) return;
    int n = 0;
    if (fscanf(f, "%d", &n) == 1) {
      n = std::max(1, std::min(n, nthreads));
      if (n != limit.load()) {
        std::lock_guard<std::mutex> l(qMu);
        limit = n;
        if ((int)queue.size() < idleOn()) wantWork = true;
        qCv.notify_all();
      }
    }
    fclose(f);
  }

  void stop() {
    std::unique_lock<std::mutex> l(qMu);
    stopReq = true;
    pauseReq = false;
    qCv.notify_all();
  }

  void writeState(Saved &saved, const std::vector<std::string> &args) {
    Saved s;
    s.args = args;
    s.fp = saved.fp;
    s.elapsed = elapsed0 + sessionSeconds();
    s.steps = steps0 + totalSteps();
    {
      std::lock_guard<std::mutex> l(repMu);
      s.printed = rep.printed;
      s.unknownOsc = rep.unknownOsc;
      for (int i = 0; i < 4; i++) s.counts[i] = rep.counts[i];
      s.maxgen = rep.maxgen;
      s.hashes.assign(rep.hashes.begin(), rep.hashes.end());
    }
    s.items.assign(queue.begin(), queue.end());
    s.items.insert(s.items.end(), snapshot.begin(), snapshot.end());
    writeCheckpoint(o.checkpoint, s);
  }

  void checkpoint(Saved &saved, const std::vector<std::string> &args) {
    pauseAll();
    try {
      writeState(saved, args);
    } catch (const std::exception &e) {
      fprintf(stderr, "\nwarning: %s\n", e.what());
    }
    resumeAll();
  }

  void clearProgressLine() {
    if (ttyProgress && progressShown) {
      fputs("\r\033[K", stderr);
      progressShown = false;
    }
  }

  void progressLine() {
    double frac, sec = sessionSeconds();
    size_t qsize;
    {
      std::lock_guard<std::mutex> l(qMu);
      frac = completed;
      for (const Worker &w : workers) frac += w.progress.load();
      qsize = queue.size();
    }
    long long st = totalSteps();
    long found, newOsc;
    int mg;
    {
      std::lock_guard<std::mutex> l(repMu);
      found = rep.counts[0] + rep.counts[1] + rep.counts[2] + rep.counts[3];
      newOsc = rep.unknownOsc;
      mg = rep.maxgen;
    }
    double done0 = frac;
    std::string eta = "?";
    double total = elapsed0 + sec;
    if (done0 > 1e-6 && done0 < 1) eta = hms(total / done0 * (1 - done0));
    char buf[256];
    snprintf(buf, sizeof buf,
             "[~%.3g%%] %.2fM steps/s, %ld results (%ld new osc), max gen %d, %zu queued, "
             "%s elapsed, eta ~%s",
             100 * frac, sec > 0 ? st / sec / 1e6 : 0.0, found, newOsc, mg, qsize,
             hms(total).c_str(), eta.c_str());
    std::lock_guard<std::mutex> l(repMu);
    if (ttyProgress) {
      fprintf(stderr, "\r%s\033[K", buf);
      progressShown = true;
    } else
      fprintf(stderr, "%s\n", buf);
    fflush(stderr);
  }
};
thread_local int Coordinator::tid = 0;

std::string exeDir(const char *argv0) {
  char buf[4096];
#ifdef __APPLE__
  uint32_t size = sizeof buf;
  if (_NSGetExecutablePath(buf, &size) == 0) {
    char real[PATH_MAX];
    if (realpath(buf, real)) {
      std::string s = real;
      return s.substr(0, s.rfind('/'));
    }
  }
#else
  ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
  if (n > 0) {
    buf[n] = 0;
    std::string s = buf;
    return s.substr(0, s.rfind('/'));
  }
#endif
  std::string s = argv0;
  size_t p = s.rfind('/');
  return p == std::string::npos ? "." : s.substr(0, p);
}

bool fileExists(const std::string &p) {
  FILE *f = fopen(p.c_str(), "r");
  if (f) fclose(f);
  return f != nullptr;
}

}  // namespace

int main(int argc, char **argv) {
  std::vector<std::string> args(argv + 1, argv + argc);
  if (args.empty()) {
    printf("drift: search Life-like rules for oscillators, sparkers, catalysts and signals.\n\n"
           "  drift CONFIG               run a search described in CONFIG (see docs/GUIDE.md)\n"
           "  drift CONFIG --dry-run     show the starting position without searching\n"
           "  drift survey RULE          run a battery of searches in RULE and summarise the finds\n"
           "  drift finish CONFIG        complete and check a search's results (also render,\n"
           "                             validate, wirecheck, wirebuild: the tools/ scripts)\n"
           "  drift --help               all options\n\n"
           "Example: drift examples/beehive-spark.cfg\n");
    return 0;
  }
  // drift survey|finish|render|validate|wirecheck|wirebuild ...: run tools/<name>.py
  static const char *tools[] = {"survey", "finish", "render", "validate", "wirecheck", "wirebuild"};
  for (const char *t : tools)
    if (args[0] == t && !fileExists(args[0])) {
      std::string script = exeDir(argv[0]) + "/tools/" + t + ".py";
      std::vector<std::string> cmd = {"python3", script};
      cmd.insert(cmd.end(), args.begin() + 1, args.end());
      std::vector<char *> cargv;
      for (std::string &c : cmd) cargv.push_back(&c[0]);
      cargv.push_back(nullptr);
      execvp("python3", cargv.data());
      fprintf(stderr, "drift: can't run python3 %s\n", script.c_str());
      return 1;
    }
  Options o;
  Saved saved;
  bool resumed = false;
  std::vector<Item> items;

  try {
    auto it = std::find(args.begin(), args.end(), "--classic");
    if (it != args.end()) {
      args.erase(it);
      o.classic = true;
      o.perRotor = 0;
      std::vector<std::string> classicArgs;
      for (size_t i = 0; i < args.size(); i++) {   // drift options may be mixed in
        if (args[i] == "--threads" && i + 1 < args.size()) o.threads = atoi(args[++i].c_str());
        else if (args[i] == "--quiet") o.quiet = true;
        else if (args[i] == "--max-steps" && i + 1 < args.size()) o.maxSteps = atoll(args[++i].c_str());
        else classicArgs.push_back(args[i]);
      }
      readClassic(classicArgs, std::cin, o);
      if (!o.threads) o.threads = 1;
      o.progressEvery = 1e9;
      o.quiet = o.quiet || o.threads == 1;
    } else {
      if (!readModern(args, o)) return 0;
      if (!o.resume.empty()) {
        saved = readCheckpoint(o.resume);
        std::vector<std::string> extra;
        for (size_t i = 0; i < args.size(); i++) {
          if (args[i] == "--resume") { i++; continue; }
          if (args[i].compare(0, 9, "--resume=") == 0) continue;
          extra.push_back(args[i]);
        }
        std::vector<std::string> all = saved.args;
        all.insert(all.end(), extra.begin(), extra.end());
        std::string ckpt = o.resume;
        o = Options();
        readModern(all, o);
        if (fingerprint(o) != saved.fp)
          throw std::runtime_error("the search settings differ from the checkpoint's (did the "
                                   "config or pattern file change?)");
        if (o.checkpoint.empty()) o.checkpoint = ckpt;
        args = saved.args;
        items = saved.items;
        resumed = true;
        if (items.empty()) {
          printf("The search saved in '%s' is already complete.\n", ckpt.c_str());
          return 0;
        }
      }
      saved.fp = fingerprint(o);
    }

    // Known rotors: dr2.c's list is for B3/S23.
    KnownRotors known;
    bool isLife = o.rule.canonical() == "B3/S23";
    std::string file = o.knownRotorsFile.empty() ? "knownrotors" : o.knownRotorsFile;
    if (o.knownRotorsExplicit || o.classic || isLife) {
      std::string path = file;
      if (!fileExists(path) && file.find('/') == std::string::npos)
        path = exeDir(argv[0]) + "/" + file;
      std::string err;
      if (fileExists(path)) {
        if (!known.load(path, err)) throw std::runtime_error(err);
        o.knownRotorsFile = path;
      } else if (o.knownRotorsExplicit)
        throw std::runtime_error("can't open known rotors file '" + file + "'");
      else {
        if (o.classic) fprintf(stderr, "warning: can't open known rotors file '%s'\n", file.c_str());
        o.knownRotorsFile = file;
      }
    }

    Search base;
    base.init(o.params, &o.rule, &known);
    base.start();
    if (!o.classic && base.nays[0] > base.chgd[0]) {   // can drift build anything near the spark?
      bool unknownNear = false;
      for (int q = base.chgd[0]; q < base.nays[0] && !unknownNear; q++)
        for (int dr = -2; dr <= 2 && !unknownNear; dr++)
          for (int dc = -2; dc <= 2 && !unknownNear; dc++)
            unknownNear = base.bkgd[base.idx(base.chglist[q].r + dr, base.chglist[q].c + dc)] == UNK;
      std::vector<std::pair<int, int>> spark;
      for (int q = base.chgd[0]; q < base.nays[0]; q++)
        if (base.curr[base.idx(base.chglist[q].r, base.chglist[q].c)] == ON)
          spark.push_back({base.chglist[q].r, base.chglist[q].c});
      if (!unknownNear && !isSpaceship(o.rule, spark))
        o.warnings.push_back("every cell within 2 of the spark is known, so drift can't build anything "
                             "until the spark's own evolution reaches unknown cells (it may outgrow the "
                             "limits first). Leave unknown cells next to the spark where things may be built "
                             "(ignore this if the spark is meant to fly through empty space first).");
    }
    if (resumed) o.freshJsonl = o.freshText = false;
    if (o.dryRun) o.jsonl.clear(), o.textOut.clear();   // a dry run never opens (or empties) result files

    int threads = o.threads > 0 ? o.threads : (int)std::max(1u, std::thread::hardware_concurrency());
    Reporter rep(o, &known, known.names.size());
    rep.finishScript = exeDir(argv[0]) + "/tools/finish.py";
    if (resumed) {
      rep.hashes.insert(saved.hashes.begin(), saved.hashes.end());
      rep.printed = saved.printed;
      rep.unknownOsc = saved.unknownOsc;
      rep.maxgen = saved.maxgen;
      for (int i = 0; i < 4; i++) rep.counts[i] = saved.counts[i];
      printf("Resuming '%s': %zu subtrees left, %ld results so far.\n", o.checkpoint.c_str(),
             items.size(), saved.printed);
    }
    rep.header(base, threads);
    if (o.dryRun) return 0;
    if (!resumed) items.push_back({{}, 1.0});

    if (!o.classic) {
      signal(SIGINT, onSignal);
      signal(SIGTERM, onSignal);
    }
    int active = threads;
    if (!o.threadsFile.empty()) {   // start as many threads as could ever be asked for
      if (o.threads <= 0) threads = (int)std::max(1u, std::thread::hardware_concurrency());
      if (FILE *f = fopen(o.threadsFile.c_str(), "r")) {
        if (fscanf(f, "%d", &active) != 1) active = threads;
        fclose(f);
      }
      active = std::max(1, std::min(active, threads));
    }
    Coordinator co(rep, base, o, threads, active);
    bool finished = co.run(items, saved, args);
    long long steps = co.totalSteps();
    if (o.classic) {
      if (threads == 1) printf("computecellorbackup calls: %ld %06ld\n", co.lastHi, co.lastLo);
      else printf("computecellorbackup calls: %lld %06lld\n", steps / 1000000, steps % 1000000);
    }
    rep.footer(co.sessionSeconds(), steps, finished, resumed);
    if (!o.classic && !o.noFinish && rep.printed > 0 && !o.configPath.empty() && !gSignal.load() &&
        o.jsonl.empty())
      printf("\nNot finishing the results: they weren't saved (--no-save).\n");
    else if (!o.classic && !o.noFinish && rep.printed > 0 && !o.configPath.empty() && !gSignal.load()) {
      // finish.py reads the config file; settings given on the command line reach it here
      std::string extra;
      for (const std::string &l : cliSettings(args)) extra += l + "\n";
      setenv("DRIFT_EXTRA_SETTINGS", extra.c_str(), 1);
      // Started directly (not through a shell), so any file name is passed as it is.
      std::vector<std::string> fa = {"python3", rep.finishScript, o.configPath};
      std::string base = o.configPath;
      if (base.size() > 4 && base.compare(base.size() - 4, 4, ".cfg") == 0) base.resize(base.size() - 4);
      if (o.jsonl != base + "-results.jsonl") fa.insert(fa.end(), {"--jsonl", o.jsonl});
      fa.insert(fa.end(), {"--jobs", std::to_string(threads)});
      printf("\nFinishing the results (tools/finish.py; --no-finish skips this)...\n");
      fflush(stdout);
      fflush(stderr);
      int status = -1;
      pid_t pid = fork();
      if (pid == 0) {
        std::vector<char *> av;
        for (std::string &x : fa) av.push_back(&x[0]);
        av.push_back(nullptr);
        execvp("python3", av.data());
        _exit(127);
      }
      if (pid > 0) waitpid(pid, &status, 0);
      if (!(pid > 0 && WIFEXITED(status) && WEXITSTATUS(status) == 0)) {
        std::string cmd;
        for (const std::string &x : fa) cmd += (cmd.empty() ? "" : " ") + ("\"" + x + "\"");
        printf("finish.py didn't complete. Run it yourself with:\n  %s\n", cmd.c_str());
      }
    }
    // 0: complete, or stopped at a limit you set (--max-time, --max-steps); 130: Ctrl-C
    return gSignal.load() ? 130 : 0;
  } catch (const std::exception &e) {
    fflush(stdout);
    fprintf(stderr, "drift: %s\n", e.what());
    return 1;
  }
}
