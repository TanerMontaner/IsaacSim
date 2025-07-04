# Changelog
## [2.0.7] - 2025-05-31
### Changed
- Use default nucleus server for all tests

## [2.0.6] - 2025-05-30
### Changed
- Update golden values for unit test

## [2.0.5] - 2025-05-19
### Changed
- Update copyright and license to apache v2.0

## [2.0.4] - 2025-05-16
### Changed
- Make extension target a specific kit version

## [2.0.3] - 2025-05-10
### Changed
- Remove internal build time dependency

## [2.0.2] - 2025-05-07
### Changed
- switch to omni.physics interface

## [2.0.1] - 2025-05-03
### Fixed
- Fix issues where name override was incorrectly used if set to empty string

## [2.0.0] - 2025-05-02
### Changed
- Move all dynamic control related header/utilities/bindings to this extension from isaacsim.core.includes and isaacsim.core.utils

## [1.3.24] - 2025-04-11
### Changed
- Update default asset root path

## [1.3.23] - 2025-04-04
### Changed
- Version bump to fix extension publishing issues

## [1.3.22] - 2025-03-26
### Changed
- Cleanup and standardize extension.toml, update code formatting for all code

## [1.3.21] - 2025-03-25
### Changed
- Add import tests for deprecated extensions

## [1.3.20] - 2025-03-05
### Changed
- Update extension codebase to adhere to isaac sim extension structure and file naming  guidelines

## [1.3.19] - 2025-03-04
### Changed
- Update to kit 107.1 and fix build issues

## [1.3.18] - 2025-02-25
### Changed
- Update style format and naming conventions in c++ code, add doxygen docstrings

## [1.3.17] - 2025-02-14
### Fixed
- UR10 unit test

## [1.3.16] - 2025-01-28
### Fixed
- Windows signing issue

## [1.3.15] - 2025-01-26
### Changed
- Update test settings

## [1.3.14] - 2025-01-21
### Changed
- Update extension description and add extension specific test settings

## [1.3.13] - 2024-11-18
### Changed
- omni.client._omniclient to omni.client

## [1.3.12] - 2024-11-15
### Changed
- Fix unit test

## [1.3.11] - 2024-10-30
### Changed
- Add profiler marker

## [1.3.10] - 2024-10-28
### Changed
- Remove test imports from runtime

## [1.3.9] - 2024-10-24
### Changed
- Updated dependencies and imports after renaming

## [1.3.8] - 2024-06-14
### Fixed
- Unit test fixes

## [1.3.7] - 2024-05-11
### Changed
- Renamed Transporter to iw.hub

## [1.3.6] - 2024-05-03
### Fixed
- Update IStageUpdate usage to fix deprecation error
- Update golden values for franka test

## [1.3.5] - 2024-04-15
### Changed
- Removed the use of deprecated physX jointSolverForces

## [1.3.4] - 2024-03-07
### Changed
- Deprecated the extension and removed its usage in other extensions in python

## [1.3.3] - 2024-03-06
### Changed
- Updated path to ur10

## [1.3.2] - 2024-02-02
### Changed
- Updated path to the nucleus extension

## [1.3.1] - 2024-01-18
### Changed
- Changed get_assets_root_path to get_assets_root_path_async for the unit tests

## [1.3.0] - 2024-01-08
### Changed
- Moved header files to extension

## [1.2.6] - 2023-12-12
### Fixed
- Issue with prim getting removed at random

## [1.2.5] - 2023-08-04
### Fixed
- Fixed joints on the root of an articulation are treated as a special type of internal articulation to support fixed base.
- Getting the type for the first fixed joint on the root link of an articulation will return none now
- Use USD apis to interact with the first fixed joint on the root of an articulation.

## [1.2.4] - 2023-06-12
### Changed
- Update to kit 105.1, update build system
- set_time_codes_per_second in set_physics_frequency

## [1.2.3] - 2023-01-21
### Fixed
- Fix when multiple objects shared the same prim name using the isaac:nameOverride attribute for get_name

## [1.2.2] - 2022-10-20
### Fixed
- test golden values

## [1.2.1] - 2022-10-17
### Fixed
- explicitly handle prim deletion

## [1.2.0] - 2022-09-27
### Changed
- tests to use nucleus assets

### Removed
- usd files local to extension

## [1.1.1] - 2022-09-07
### Fixed
- Fixes for kit 103.5

## [1.1.0] - 2022-08-12
### Added
- cMassLocalPose to DcRigidBodyProperties

## [1.0.1] - 2022-08-09
### Changed
- Removed simple_articulation.usd, test_articulation_simple uses Nucleus asset

## [1.0.0] - 2022-05-11
### Changed
- non-backwards compatible change: dof indexing matches physx tensor API

## [0.2.2] - 2022-04-29
### Fixed
- Handle physx unwrapped revolute joints

## [0.2.1] - 2022-02-13
### Fixed
- Properly delete handles on prim deletion

## [0.2.0] - 2022-01-14
### Fixed
- Error message when waking up a kinematic rigid body
- Error message when setting linear velocity on a body with simulation disabled
- Error message when setting angular velocity on a body with simulation disabled

## [0.1.8] - 2021-08-16
### Added
- get_effort
- get_articulation_dof_efforts
- apply_body_torque

### Fixed
- inconsistent return types
- crash when stepping with a zero timestep as first step

### Changed
- apply_effort -> set_effort
- apply_articulation_dof_efforts -> set_articulation_dof_efforts
- handle refresh messages are printed out as info messages, instead of always printing
- apply_body_force now has a bool to specify if the force is global or local

## [0.1.7] - 2021-08-16
### Added
- Sleep functions for rigid bodies and articulations

### Changed
- return types use size_t instead of int where appropriate

## [0.1.6] - 2021-08-04
### Changed
- DriveMode is now either DRIVE_FORCE or DRIVE_ACCELERATION, default is acceleration
- Position/Velocity drive is not specified via DriveMode
- All API calls verify if simulating, return otherwise
- set_dof_properties will not enable or change drive limits
- set_dof_state takes StateFlags to apply specific states
- get_dof_state takes StateFlags to set which states to get

### Added
- State variables can be printed
- ArticulationProperties to control articulation settings
- RigidBodyProperties can control iteration counts and contact impulse settings
- get_articulation_properties
- set_articulation_properties
- get_articulation_dof_position_targets
- get_articulation_dof_velocity_targets
- get_articulation_dof_masses
- set_rigid_body_properties
- get_dof_properties
- unit tests for most articulation, rigid body, dof and joint apis
- utilities for common scene setup and testing

### Removed
- get_articulation_dof_state_derivatives
- DriveModes DRIVE_NONE, DRIVE_POS, DRIVE_VEL

### Fixed
- apply_body_force now applies a force at a point
- set_dof_properties does not break position/velocity drives
- dof efforts report correct forces/torques due to gravity
- when changing state of a dof or a root link, unrelated state values are not applied anymore
- set_dof_state applies efforts now
- get_dof_properties works correctly now

## [0.1.5] - 2021-07-23
### Added
- Split samples from extension

## [0.1.4] - 2021-07-14
### Added
- now works when running without editor/timeline and only physx events.
- fixed crash with setting dof properties

## [0.1.3] - 2021-05-24
### Added
- force and torque sensors

## [0.1.2] - 2021-02-17
### Added
- update to python 3.7
- update to omni.kit.uiapp

## [0.1.1] - 2020-12-11
### Added
- Add unit tests to extension

## [0.1.0] - 2020-12-03
### Added
- Initial version of Isaac Sim Dynamic Control Extension
