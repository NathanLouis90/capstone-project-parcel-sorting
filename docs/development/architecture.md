# Parcel sorting architecture

Receiving supplies one parcel with arbitrary position and yaw. Manual medium
selection chooses one pick-to-scan policy: envelope (both arms, right holds),
poly mailer (both arms, right holds), or carton (left holds). ACT and DP share the policy-step
contract: `reset()`, then `step({qpos, images}) -> 14 joint/gripper commands`.
A future classifier or VLA adapter can use the same supervisor boundary.

Envelope demonstrations learn a 180° carry flip when the label faces upwards.
For a top-facing mailer, the left arm flips it on a fixed elevated platform;
the right then grasps a corner and carries to scan while the left returns home.
Bottom-facing mailers skip the flip. Both policy arms remain enabled for mailers.
Carton scanning uses scripted wrist rotation. A shared FK and settling check
ends learned execution before scanner-driven rotation and placement begin.
No token, bin, or label-face metadata enters policy observations.

Taught joint paths handle bins, receiving returns and home through the same
validated 25 Hz motion stream. Runtime FK checks constrain jaw tips; physical
commissioning must cover the parcel body, fixtures, inter-arm clearance and
cable travel. Gripper feedback is currently a command estimate, so physical
outcomes require an operator.

A no-read returns the parcel to receiving, releases it at a taught low height
and returns home. One linked retry is allowed. Faults stop both controllers and
require inspection before manual recovery. CSV timing excludes operator input.

Current data collection uses 50 fresh accepted demonstrations per medium and
matched ACT/DP train/validation partitions.
