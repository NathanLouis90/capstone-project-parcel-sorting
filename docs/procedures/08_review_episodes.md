# Review episodes

The result is every recording in a project marked `accepted` or `rejected`, ready for the training menu.

## Before you start

- Finish [recording](07_record_episodes.md) and stop the recorder. No robot server is needed; review never moves the robot.
- Open one terminal with a graphical display:
  ```bash
  conda activate Xtrainer
  cd ~/dobot_xtrainer
  ```
- Only review recordings you made yourself. Observation files are trusted local pickles.

## Steps

1. Count the recordings in every project.
   ```bash
   python3 tools/count_episodes.py --details
   ```
   Expect: one row per project with Total, Complete, Incomplete and Unknown counts, then one line per episode with its medium, label face and review status.

2. Open the unreviewed episodes of one project. Replace `poly_mailer_bottom` with the project folder you recorded.
   ```bash
   python3 recording/review_episodes.py --project datasets/poly_mailer_bottom
   ```
   Expect: a window with the top, left-wrist and right-wrist views playing side by side.

3. Watch each episode for a home start, prompt motion, a secure grasp, the correct label face, and a still scan pose at the end with the other arm home.
4. Focus the video window and press a key: `a` accept, `r` reject, `s` skip, `p` replay, space pause, `q` quit.
   Expect: `Marked accepted` or `Marked rejected`; the decision is saved immediately.
5. Read any `[Warn]:` lines printed on acceptance (start not home, scan pose not held, rate). If the decision was wrong, revisit it in step 6.
   Expect: `Review results:` with the counts when the last episode is done.

## Revisit earlier decisions

6. Review every episode again, including accepted and rejected ones.
   ```bash
   python3 recording/review_episodes.py --project datasets/poly_mailer_bottom --include-reviewed
   ```
   Expect: playback starts from the first episode. Use `--only-rejected` instead to see only rejections.

7. Open specific episodes. Replace `EPISODE_ID` with a folder name under `collect_data/`.
   ```bash
   python3 recording/review_episodes.py --project datasets/poly_mailer_bottom --episodes EPISODE_ID
   ```
   Expect: only that episode plays.

## Apply a decision without playback

8. Preview a batch decision for episodes you have already inspected.
   ```bash
   python3 recording/review_episodes.py --project datasets/poly_mailer_bottom \
     --episodes EPISODE_ID --set-status rejected --dry-run
   ```
   Expect: `Would mark rejected` and `Dry-run checks:`.
9. Run the same command without `--dry-run` to apply it.
   Expect: `Marked rejected`.

Continue with [train models](09_train_models.md), which also deletes rejected recordings and moves overflow.
For playback, review statuses and end checks, see [datasets reference](../reference/datasets.md#review-decisions-and-end-checks).

## If something goes wrong

- `No graphical display` -> run from a desktop session, or inspect recordings elsewhere and add `--terminal-only`.
- `No episodes selected` -> everything is already reviewed; add `--include-reviewed`.
- `Use --only-rejected or --include-reviewed, not both` -> keep only one of the two options.
- `--dry-run requires --set-status or --sync-review-status` -> dry runs apply only to batch decisions.
- `[Error]: ... Missing frames or camera/observation identifiers do not match` -> the episode is incomplete; reject it.
- `Scan pose is unconfigured; teach scan_right` (or `scan_left`) -> [teach the waypoint](05_teach_waypoints.md) before recording more.
