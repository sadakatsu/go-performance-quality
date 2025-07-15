## go-performance-quality
**go-performance-quality © 2025 by Joseph "sadakatsu" Craig ([the.sadakatsu@gmail.com](the.sadakatsu@gmail.com)) is
licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International. To view a copy of this license,
visit
[https://creativecommons.org/licenses/by-nc-sa/4.0/](https://creativecommons.org/licenses/by-nc-sa/4.0/)**

The purpose of this repository is to help Go students study games.  It acts as a targeted
[KataGo](https://github.com/lightvector/KataGo) wrapper to provide more helpful feedback.  It currently provides three
different executables (listed in expected order of user interest):

- **GoStudy**: This program assesses how well each player played using KataGo's human profiles, reviews the players
  according to their performance levels, and reduces the study recommendations to the _N_ worst mistakes to try to
  accelerate the student's growth.
- **Process**: This program is intended for generating a clean JSON report for consumption into a database.  Most users
  are unlikely to care about anything other than the `performances` section.  This captures the players' performances
  over the entire game, the opening (moves 1-50), the middle game (moves 51-150), and the endgame (moves 151+).  This
  can provide some additional guidance for what area of the game to focus on.  It also generates a nice Markdown table
  that one can send to server admins as evidence of cheating or sandbagging.
- **Classic**: This program generates a nice infographic view of the game, intended to highlight the moves at which
  players made their worst mistakes without giving the answer as to how.  Even I have stopped using this very much after
  developing GoStudy.  If you want to create a book of your games over time, this could be nice to use.

### Setting up to use this repository
1. Navigate to the [KataGo](https://github.com/lightvector/KataGo/releases) releases page to download the version of
   KataGo that best matches your hardware.  Note that this depends upon the human profile capabilities, so you must use
   no earlier a version than 1.15.0.  I am using 1.16.0 as of 2025-07-15 (which is already a few patch versions behind).
2. Download two KataGo models:
    - [an up-to-date play network](https://katagotraining.org/networks/) .  I strongly recommend going for a shallower
      network (e.g. `b18`) with a decent number of channels (e.g. `c384`) such as
      [kata1-b18c384nbt-s9996604416-d431659742](https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz) .
      These applications depend upon deep analysis using high visit counts, so using deeper networks will slow down the
      analysis considerably without improving the results much (or at all!).
    - [the human profile network](https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz)
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
7. Build a new Python environment, installing this program's dependencies: `conda env create -f environment.yml`
8. Modify `configuration/application.yaml` so the `katago` subproperties are correct.  You may also want to change your
   `analysisThreads` value.  If you have a powerful, tensor-core equipped GPU, and you tend to analyze longer games,
   bumping your analysis threads to 32 can get you better throughput.  If you don't have a recent graphics card or use
   more economical models, you may want to reduce this to 8 or even 4.  Keep in mind that each one of these threads will
   review one position at a time, so you will find diminishing returns for increasing this value ever higher.  I have
   noticed no benefit to using any values other than binary powers.  Also, for no reason I understand, using two
   analysis threads does not better than using one.

### Running one of the programs
1. Open up a terminal/command prompt.
2. `conda activate goperformance4`
3. `cd` into your local checkout of this repository.
4. Refer to the following sections for how to run and use the three different execution paths.

If you have not run a specific SGF file through any of these programs before, this will kick off a deep KataGo review of
the game.  Letting this finish will result in a CSV file that any future runs will reuse.

Note: When running any of these programs, you will see warnings like these:

```C:\Users\josep\miniconda3\envs\goperformance4\Lib\site-packages\sklearn\base.py:380: InconsistentVersionWarning: Trying to unpickle estimator LinearDiscriminantAnalysis from version 0.24.2 when using version 1.6.1. This might lead to breaking code or invalid results. Use at your own risk. For more info please refer to:
https://scikit-learn.org/stable/model_persistence.html#security-maintainability-limitations
  warnings.warn(
C:\Users\josep\miniconda3\envs\goperformance4\Lib\site-packages\sklearn\base.py:380: InconsistentVersionWarning: Trying to unpickle estimator PCA from version 0.24.2 when using version 1.6.1. This might lead to breaking code or invalid results. Use at your own risk. For more info please refer to:
https://scikit-learn.org/stable/model_persistence.html#security-maintainability-limitations
  warnings.warn(
```

These are because I trained the Quality Score and Damage models used in this program using an older environment.  I need
to fix this at some point.  However, they do not negatively affect how this program runs.

### Running GoStudy
`python go_study.py {path to SGF file} {name of player to review for or "both"} {number of mistakes to study}`

The second two arguments are optional.  If you omit the last argument, it will keep 3 mistakes per player reviewed.  If
you omit both arguments, it will review both players.  I recommend passing `{your username} 5` to get a good review
without being distracted by feedback for your opponent.

This program assesses how strongly each player played in the match by matching the moves selected against many the
post-AlphaGo human profiles.  It uses the mean profile to filter move recommendations during the review and to classify
moves for value in studying those moves.

This generates three files:
1. `{original name}_study.sgf` - the study variation of the source file.  The hope is that you can improve by studying
   the recommended positions and explaining to yourself why the recommended moves are better than the move you played.
2. `{original name}_complete.sgf` - a complete review of the source file.  This is definitely information overload.  It
   can be useful for trying to answer questions like, "How well did I play overall?" or "Why was this move skipped for
   review?"
3. `{original name}-rating-probabilities.png` - a graph that shows the probability that each player performed at each of
   the assessed performance ratings.  

Note that no individual game is likely to capture your true rating.  Each player has different strengths and weaknesses.
Games that have higher performance ratings likely played to your strengths, whereas games with lower performance ratings
reveal your weaknesses.  Tracking your performances over time, especially if you play frequently and consistently, will
reveal your "true" rating.  Focus more heavily on low performance games to eliminate weaknesses.  Compare high and low
game sets against each other to identify your strengths and to help you cultivate your style.

While the review SGFs should work with any SGF viewer, I strongly recommend using
[Sabaki](https://sabaki.yichuanshen.de/).  Sabaki processes Markdown when rendering the comments, so the reviews are
more readable.  More importantly, **it generates hyperlinks from the first comment directly to the moves to study**.
This makes reviewing the study file much quicker.

### Running Process
`python process_game.py {path to SGF file}`

This generates a file `{original_name}.json` that summarizes the KataGo review of the game.  This program is likely most
interesting because it generates a Markdown table during its execution that describes the players' performances like so:

```Overall:
| Metric           | Black                | White                |
|------------------|----------------------|----------------------|
| Probable Rating  | 2k (51.52%)          | 3k (52.65%)          |
| Rating Range     | 2.61k ± 0.74         | 3.16k ± 0.65         |
| Accuracy         |               52.96% |               40.01% |
| Best Move %      |               39.78% |               33.70% |
| Match %          |               54.84% |               53.26% |
| Drop Mean        |                2.29% |                2.41% |
| Loss Mean        |                2.88  |                3.08  |
| Quality Score    |               43.87  |               35.69  |
| Simplicity Score |               34.31  |               24.14  |
|------------------|----------------------|----------------------|
| <0.5             |             44 ( 28) |             38 ( 21) |
| ≥0.5             |             11 ( 39) |             13 ( 34) |
| ≥1.5             |             10 ( 16) |             15 ( 27) |
| ≥3.0             |             12 (  3) |             12 (  7) |
| ≥6.0             |             12 (  7) |              9 (  0) |
| ≥12.0            |              4 (  0) |              5 (  3) |

Opening:
| Metric           | Black                | White                |
|------------------|----------------------|----------------------|
| Probable Rating  | 2d (33.54%)          | 3k (20.54%)          |
| Rating Range     | 2.80d ± 1.22         | 3.68k ± 2.55         |
| Accuracy         |               46.05% |               43.66% |
| Best Move %      |               36.00% |               36.00% |
| Match %          |               52.00% |               52.00% |
| Drop Mean        |                4.49% |                3.72% |
| Loss Mean        |                0.97  |                0.84  |
| Quality Score    |               70.08  |               69.01  |
| Simplicity Score |               78.22  |               80.28  |
|------------------|----------------------|----------------------|
| <0.5             |             14 ( 17) |             13 ( 18) |
| ≥0.5             |              5 (  7) |              5 (  6) |
| ≥1.5             |              3 (  1) |              6 (  1) |
| ≥3.0             |              2 (  0) |              1 (  0) |
| ≥6.0             |              1 (  0) |              0 (  0) |
| ≥12.0            |              0 (  0) |              0 (  0) |

Middle:
| Metric           | Black                | White                |
|------------------|----------------------|----------------------|
| Probable Rating  | 5k (31.99%)          | 3k (54.03%)          |
| Rating Range     | 5.41k ± 1.34         | 3.56k ± 0.74         |
| Accuracy         |               47.11% |               34.68% |
| Best Move %      |               34.00% |               28.00% |
| Match %          |               48.00% |               50.00% |
| Drop Mean        |                1.97% |                2.54% |
| Loss Mean        |                2.89  |                3.29  |
| Quality Score    |               32.96  |               26.99  |
| Simplicity Score |               36.38  |               17.25  |
|------------------|----------------------|----------------------|
| <0.5             |             19 ( 11) |             16 (  3) |
| ≥0.5             |              6 ( 28) |              6 ( 27) |
| ≥1.5             |              6 ( 10) |              9 ( 18) |
| ≥3.0             |              8 (  1) |             10 (  2) |
| ≥6.0             |             11 (  0) |              8 (  0) |
| ≥12.0            |              0 (  0) |              1 (  0) |

End:
| Metric           | Black                | White                |
|------------------|----------------------|----------------------|
| Probable Rating  | AI (94.51%)          | 1d (23.52%)          |
| Rating Range     | AI (~11.30d) ± 1.00  | 1.47d ± 1.91         |
| Accuracy         |               70.94% |               42.97% |
| Best Move %      |               61.11% |               47.06% |
| Match %          |               77.78% |               64.71% |
| Drop Mean        |                0.09% |                0.12% |
| Loss Mean        |                5.47  |                5.75  |
| Quality Score    |               57.92  |               40.81  |
| Simplicity Score |              -10.08  |               -7.89  |
|------------------|----------------------|----------------------|
| <0.5             |             11 (  0) |              9 (  0) |
| ≥0.5             |              0 (  4) |              2 (  1) |
| ≥1.5             |              1 (  5) |              0 (  8) |
| ≥3.0             |              2 (  2) |              1 (  5) |
| ≥6.0             |              0 (  7) |              1 (  0) |
| ≥12.0            |              4 (  0) |              4 (  3) |
```

This information is also captured in the JSON report.  (I played Black in the game above. I promise I wasn't actually
cheating in that endgame!  I made 4 12+ point mistakes in 18 moves for a Loss Mean of 5.47 points.)

Most of these statistics are likely familiar if you have used programs like [AI Sensei](https://ai-sensei.com/),
[KaTrain](https://github.com/sanderland/katrain/), or [LizzieYZY](https://github.com/yzyray/lizzieyzy).  Note that my
numbers are different from these other programs' results primarily because I handle symmetries and allow moves that have
minor loss compared to other moves to be treated as equivalent.  This both gives a better measure for how well one
played and provides better cheat detection.

The statistics you likely have not seen before are:
- `Quality Score`: a score I developed that measures how frequently a player makes mistakes and how large they tend to
  be.  `100+` is superhuman, `70+` tends to be high dan or pro, `70` means both players missed something urgent the
  entire game, `50` is the median, and `~48` is the mean.  You can read `documentation/old_README.md` for a detailed
  explanation about how to interpret it and how I created it.
- `Simplicity Score`: a Quality Score that is calculated using KataGo's policy values to calculate expected losses; this
  roughly measures how easy a game is and thus gives context to how well a player's Quality Score should be viewed

### Running Classic
`python main.py {path to SGF file}`
This generates an infographic file like the one you see in the `infographics/` directory.  You can read the
`documentation/old_README.md` to learn about how to interpret that infographic.

### Issues
I am in the middle of hacking this code in two different directions right now.  I cannot guarantee that this code is
functioning as well as it used to.  If you try to run this program and encounter any difficulties, please E-mail me at
[the.sadakatsu@gmail.com](the.sadakatsu@gmail.com) .  I will try to respond and fix issues as quickly as I can.