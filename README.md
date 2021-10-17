# go-performance-quality

Analyze Go games to generate metrics representing how well each player played.

| Performance Table | Expected Result Graph | Estimated Mistake Distribution |
| --- | --- | --- |
| <img src="renders/2021-09-12__19x19-7.5-Nie Weiping-9p-vs-Cho Hunhyun-9p__3b06-gokifu-20210912-Nie_Weiping-Cho_Hunhyun.png" height="500" /> | <img src="plots/2021-09-12__19x19-7.5-Nie Weiping-9p-vs-Cho Hunhyun-9p__3b06-gokifu-20210912-Nie_Weiping-Cho_Hunhyun__er.png" height="500"/> | <img src="plots/2021-09-12__19x19-7.5-Nie Weiping-9p-vs-Cho Hunhyun-9p__3b06-gokifu-20210912-Nie_Weiping-Cho_Hunhyun__kde.png" height="500"/> |

### WARNING: This is _not_ distributed under a standard open-source software license.

> © 2021 Joseph Craig <the.sadakatsu@gmail.com>

This is an experimental project that I intend to turn into a full product.  I am releasing this code so that people can
use this tool for personal use.  If you wish to use this software, you may use the code to analyze Go games, and may
make minor modifications to this code to improve your personal edification.

Please do not copy this code or its algorithms into a separate project, especially for commercial or research projects.
I am continuing to develop these ideas in the hopes of being able to create a service using these ideas or possibly to
publish journal articles if I can get this process to be more powerful.  I have been working on this process for at
least a year now.  It would be painful for someone to grab this and profit off my work.

I do want people to be able to use this, so I am releasing this under an honor system.  I cannot enforce any license
that guarantees noncompete with me, so I will not even try.  Besides, the intent is to make something useful and 
helpful.  If you want to use this software in a way that I do not intend or condone, know that you could harm me.  That
should be sufficient to protect fair use.

Yes, I know _should_ is neither _must_ nor _will_.

Sadly, I must claim all standard legal protections in any event that one's use of this software does not provide the
results they wanted, regardless of the severity of their outcome.

If you are interested in collaborating or wish to request permission to use some portion of this project for a different
purpose than I generally described above, please contact me at `the DOT sadakatsu AT gmail DOT com`.

### Explanation
This project is a research effort to determine whether it is possible to assess how well players performed in a Go game.
It generates a single scalar value that I call the Quality score for each performance in a game that provides a
semi-objective means of comparing how one played across different games.

The gist of the Quality score is that it is better to make smaller mistakes than larger ones, and even better to not
mistakes at all.  It is a complicated linear transformation of the features that can be observed from a KataGo review.
I have found that it does a pretty good (not perfect!) job of giving me some good perspective on whether I played well
in a particular game.  Quality scores are continuous values (rounded to the thousandth's place), so they naturally
capture uncertainty for the comparisons.

These values are not manually bounded, but all the games I have analyzed with this algorithm have generated scores in
the range of `(-10, +10)`.  You can basically expect that a larger difference between two performances indicates greater
certainty that one performance is reliably more free of mistakes than another.  A difference of at least `0.5` has
empirically shown to capture that a player played markedly better than the other.  I am currently investigating whether
differences greater than `1` indicate that one player played stones stronger than the other (e.g., when I play against
a mid-dan, they tend to score at least `2` better than I, an OGS 1k, do).

I recommend Quality scores for the following purposes:

1. I personally have a hard time objectively evaluating how I played.  My emotions get the best of me.  I regularly feel
   like I played a terrible game, guessing that I would have a negative Quality score, only to run the algorithm and get
   a score multiple points higher than I thought.  Thus, the Quality score is good at giving a different perspective on
   one's performances, regardless of whether one uses it for the other purposes listed below or even agrees with the
   assessment.
2. These Quality scores do a good job of comparing an individual player's performances over time.  These scores captured
   when I fell into a bad slump, and gave me a way to compare games that had better scores with those with worse to find
   what changed.  I discovered that I had deviated from my old style of play; the games with higher scores were
   influence plus fighting, whereas my worst scores were when I tried to play territorial sabaki.  I started emphasizing
   my old style again, increased my average Quality score by roughly `+4`, and seem to indicate my improving at long
   last.
3. Related to the first point, this game can help identify what one does well and one does badly.  If one plays a game
   and receives a score much different than he expected, that game probably deserves a much closer look.  Abnormally
   poor performances can point out weaknesses or even blind spots in one's play.  Abnormally strong performances might
   indicate not just what one does well, but might show accidentally stumbling across a principle one did not recognize
   before.  In my case, sticking to a plan, even if it is a bad one, as opposed to flitting about trying to
   adapt to everything, though it took a dan friend to point out the differences there.
4. The Quality score is good at comparing the performances between two players for a particular game.  I have seen a few
   cases where the loser had a better Quality score.  It can be encouraging to see either that one was not outplayed too
   badly by one's opponent - or, in the case of sandbagging, to see that the discrepancy between the two players is more
   than one might have expected.

I discourage using Quality scores for the following purposes:

1. Estimating one's rating.  Stronger players are less likely to make larger mistakes, and are less likely to make
   mistakes at all.  However, the relative strength between the two players playing the game seems to have as much of an
   impact on their Quality scores as their individual strengths do.  Weaker players get punished for their mistakes more
   quickly, so they don't have sequences of missing the same key point over and over (something that is sure to flush a
   Quality score).  They are forced onto a better line of play through those punishments.  Stronger players also seem to
   play worse when playing weaker players, though I can only offer guesses as to why that is: they don't focus as much,
   they take a lead and get sloppy, they feel bad, etc.  As such, there is no clear mathematical relationship between a
   player's Quality score and one's rating.  It is better to use the Quality scores as a measure over time as described
   above, and to let whatever rating system one is using handle measuring the rating.
2. Comparing one's own performances to another person's over time.  Since these Quality scores do not clearly correlate
   to a measure of one's rating, one cannot expect to use them to compare their scores to another person's except when
   playing that person directly.  Their scores will be relative to their strength and their opponents' strengths.  It
   may be possible for two sets of players two get the same Quality scores, yet people reviewing the game could clearly
   conclude that one game was at a higher level than the other.
3. Obsessively trying to determine why one game was better than another.  This algorithm has quirks.  It favors shorter
   games over longer ones.  Not only do shorter games have fewer opportunities for mistakes, but the hyperparameter
   tuning is based upon statistical tests for whether one performance was better or worse than another.  It is difficult
   for a longer performance to avoid enough mistakes that it can be proven to be better than a short one.  Furthermore,
   this program was tuned based upon my games.  The scale/orientation of these values is therefore skewed.  I also
   discovered that testing this system with artificially awful performances (worse than 18 points lost every move) that
   the system breaks down.  This note should not discourage the use of this application, as real games prohibit players
   from having the opportunity to make such large mistakes endlessly.  It should simply be an encouragement that, if one
   cannot see why one performance might be better than another, to decide not to worry about it. 

### Set up for use

1. Navigate to the [KataGo](https://github.com/lightvector/KataGo/releases) releases page to download the version of
   KataGo that best matches your hardware.
2. Download a KataGo model. You can find the list of models that predate the KataGo Training project
   [here](https://katagotraining.org/networks/).  I recommend at least the [twenty-block, 256-channel model](
   https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b20c256x2-s5303129600-d1228401921.bin.gz).  It
   balances speed and strength well.  I discourage using a fifteen-block or shallower network, as that is likely to hurt
   the analysis quality.
3. If you downloaded an OpenCL KataGo version, I strongly recommend running a full tune. It can take many hours, but
   this program needs a deep analysis for each position to get a good assessment; whatever speed you can eke out is
   vital. You can do this by running the following command inside your KataGo directory: `katago tuner -model {MODEL YOU
   DOWNLOADED} -xsize 19 -ysize 19 -full -batchsize {256 or whatever large value your hardware can support}` . If you
   have multiple GPUs and plan to use only a subset, you may also need to add `-gpus {COMMA-SEPARATED LIST OF GPU
   IDENTIFIERS}`.
4. Copy `oracle.cfg` from this repository into your KataGo directory.
5. Install some form on Anaconda.  I use [miniconda](https://docs.conda.io/en/latest/miniconda.html), so I will write my
   guide for it.
6. Clone this repository, then navigate into that directory.
7. Build a new Python environment, installing this program's dependencies: `conda create -n goperformance
   requirements.txt`
8. Modify `configuration/application.yaml` so the `katago` subproperties are correct.  You may also want to change your
   `analysisThreads` value.  If you have a powerful, tensor-core equipped GPU, and you tend to analyze longer games,
   bumping your analysis threads to 32 can get you better throughput.  If you don't have a recent graphics card or use
   more economical models, you may want to reduce this to 8 or even 4.  Keep in mind that each one of these threads will
   review one position at a time, so you will find diminishing returns for increasing this value ever higher.  I have
   noticed no benefit to using any values other than binary powers.  Also, for no reason I understand, using two
   analysis threads does not better than using one.

### For each use:

1. Activate your conda environment: `conda activate goperformance`
2. Navigate into your repository clone.
3. Run the application: `python main.py {path to the SGF file of interest}`

You should see output like the following the first time you analyze an SGF.  If you run it for the same file multiple
times, it will reuse the past analysis and skip running KataGo again.

```
(goperformance) > python main.py C:\Users\josep\Dropbox\Kifu\stream\0263-01.sgf
Evaluating C:\Users\josep\Dropbox\Kifu\stream\0263-01.sgf...
Parsing SGF succeeded.
{'FF': 4, 'GM': 1, 'DT': '2021-08-24', 'PB': 'TotallyNotMe', 'PW': 'sadakatsu', 'BR': '1k', 'WR': '1k', 'RE': 'B+R', 'SZ': 19, 'KM': 6.5, 'RU': 'Japanese'}
Starting KataGo...
KataGo started. Sending game for analysis...
  1 moves analyzed.  Turn 10 was searched for 16384 visits; 17.741 seconds elapsed; 923.504 VPS.
  2 moves analyzed.  Turn 11 was searched for 16384 visits; 20.204 seconds elapsed; 1621.896 VPS.
  3 moves analyzed.  Turn 13 was searched for 16384 visits; 24.873 seconds elapsed; 1976.114 VPS.
## Lines removed to conserve space
  98 moves analyzed.  Turn 98 was searched for 16384 visits; 425.914 seconds elapsed; 3769.849 VPS.
  99 moves analyzed.  Turn 95 was searched for 16384 visits; 428.987 seconds elapsed; 3781.038 VPS.
  100 moves analyzed.  Turn 99 was searched for 16384 visits; 430.972 seconds elapsed; 3801.636 VPS.
All positions analyzed, compositing analysis...
Analysis complete.
Game reviewed in 430.972 seconds (1638400 total visits, 3801.636 visits per second).
Writing analysis to analyses/2021-08-24_0263-01.csv...
Analysis saved.
Player, Moves, Mistakes, p(Mistake), Loss Total, Loss Mean, Loss Std. Dev., Quality
Black, 50, 26, 0.520, 60, 1.200, 1.371, +4.358
White, 49, 31, 0.633, 79, 1.612, 1.627, +2.079

Process finished with exit code 0
```

### Interpreting the results

The program has two outputs: a table that summarizes the results, and a file that contains the by-position analysis for
the whole game.

#### The table
- `Player`: the color of the player for whom this row's stats apply
- `Moves`: how many moves the player made in this performance
- `Mistakes`: how many moves cost the player at 0.5 points from his expected endgame score
- `p(Mistake)`: the proportion of Moves that were Mistakes; `Mistakes / Moves`
- `Loss Total`: the sum of the rounded Mistake values across all the Moves this player made this performance
- `Loss Mean`: the average number of points this player lost per move
- `Loss Std. Dev.`: the standard deviation of the Loss Mean; roughly 68% of this player's moves had Mistakes that
  were within the bounds of `[Loss Mean - Loss Std. Dev., Loss Mean + Loss Std. Dev.]`
- `Quality`: the Quality score discussed above.

#### The file
The analysis produces a CSV file that tracks the expected game outcome and the mistake magnitude for each position in
the game.  It has the following columns:
- `Move`: the turn number for the current row
- `Player`: `B` if Black played this move, otherwise `W`
- `Before`: the expected score before the player made this move, reported from `Player`'s perspective; it is the
  negative value of the previous row's `After` value (except for the first row)
- `After`: the expected score after the player made this move, reported from `Player`'s perspective
- `Delta`: `Before` - `After`, the expected result's change caused by this move
- `Mistake`: `round(Delta)`, the Mistake value for this Move; it is clamped so it is never lower than zero

#### The graphics
The program generates one color-coded table and two plots.

The table captures all the same metrics that are generated in the command line.  It includes presents each player's
mistake distributions as captured by the percentiles (e.g., _x_ percent of moves cost _y_ or fewer points).  It finishes
the display by listing each player's ten worst mistakes' point costs in descending order.  This all combines to provide
a high-level overview of the players' performances and to explain why each player got the quality score that he did.
All values are color-coded in reference to the source dataset I used to calibrate the classifier.  With the exception of
`Moves`, these color codes indicate how good the value is (green/blue for best, yellow/white for average, red for either
worst possible or four standard deviations away from the average).  `Moves` is not really a quality indicator, but it is
color-coded to note how reliable the metrics generated by this program are likely to be; really short games are likely
to have inflatedly good "results".

![Cho Hunhyun 9p vs. Nie Weiping 9p Performance Table](renders/2021-09-12__19x19-7.5-Nie%20Weiping-9p-vs-Cho%20Hunhyun-9p__3b06-gokifu-20210912-Nie_Weiping-Cho_Hunhyun.png)

The first plot shows the expected result for the game for each turn combined with two graphs that show each player's worst
ten moves.  A positive _y_ value indicates Black is leading by that many points.

![Cho Hunhyun 9p vs. Nie Weiping 9p Expected Result](plots/2021-09-12__19x19-7.5-Nie%20Weiping-9p-vs-Cho%20Hunhyun-9p__3b06-gokifu-20210912-Nie_Weiping-Cho_Hunhyun__er.png)

The other plot shows the players' mistake distributions using Gaussian kernel density
estimation (KDE).  This provides a much better understanding of how each player performed than the statistical moments of `Loss Mean` and
`Loss Std. Dev.` on their own:

![Cho Hunhyun 9p vs. Nie Weiping 9p KDE](plots/2021-09-12__19x19-7.5-Nie%20Weiping-9p-vs-Cho%20Hunhyun-9p__3b06-gokifu-20210912-Nie_Weiping-Cho_Hunhyun__kde.png)

The ideal is to have a high peak reaching `y=1.0` around `x=0` to indicate an absolutely perfect game.  The more and
larger mistakes players make, the more humps will appear as `x` increases.  You can see what proportion of a players
moves each player made that cost them `x` points this way, and get an idea as to why the program generated the Quality
scores that it did.

