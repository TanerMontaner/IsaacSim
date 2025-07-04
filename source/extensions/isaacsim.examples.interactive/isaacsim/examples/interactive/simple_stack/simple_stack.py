# SPDX-FileCopyrightText: Copyright (c) 2021-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from isaacsim.examples.interactive.base_sample import BaseSample
from isaacsim.robot.manipulators.examples.franka.controllers.stacking_controller import StackingController
from isaacsim.robot.manipulators.examples.franka.tasks import Stacking


class SimpleStack(BaseSample):
    def __init__(self) -> None:
        super().__init__()
        self._controller = None
        self._articulation_controller = None

    def setup_scene(self):
        world = self.get_world()
        world.add_task(Stacking(name="stacking_task"))
        return

    async def setup_post_load(self):
        self._franka_task = self._world.get_task(name="stacking_task")
        self._task_params = self._franka_task.get_params()
        my_franka = self._world.scene.get_object(self._task_params["robot_name"]["value"])
        self._controller = StackingController(
            name="stacking_controller",
            gripper=my_franka.gripper,
            robot_articulation=my_franka,
            picking_order_cube_names=self._franka_task.get_cube_names(),
            robot_observation_name=my_franka.name,
        )
        self._articulation_controller = my_franka.get_articulation_controller()
        return

    def _on_stacking_physics_step(self, step_size):
        observations = self._world.get_observations()
        actions = self._controller.forward(observations=observations)
        self._articulation_controller.apply_action(actions)
        if self._controller.is_done():
            self._world.pause()
        return

    async def _on_stacking_event_async(self):
        world = self.get_world()
        world.add_physics_callback("sim_step", self._on_stacking_physics_step)
        await world.play_async()
        return

    async def setup_pre_reset(self):
        world = self.get_world()
        if world.physics_callback_exists("sim_step"):
            world.remove_physics_callback("sim_step")
        self._controller.reset()
        return

    def world_cleanup(self):
        self._controller = None
        return
