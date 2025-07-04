# SPDX-FileCopyrightText: Copyright (c) 2018-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
import asyncio
import gc
import os

import carb
import omni
import omni.ext
import omni.kit.app
import omni.kit.usd.layers
import omni.ui as ui
from isaacsim.asset.gen.omap.bindings import _omap
from isaacsim.asset.gen.omap.utils import compute_coordinates, generate_image, update_location
from isaacsim.core.utils.stage import get_stage_units
from isaacsim.gui.components.element_wrappers import ScrollingWindow
from isaacsim.gui.components.menu import make_menu_item_description
from isaacsim.gui.components.ui_utils import (
    btn_builder,
    cb_builder,
    color_picker_builder,
    dropdown_builder,
    float_builder,
    multi_btn_builder,
    xyz_builder,
)
from omni.kit.menu.utils import (
    MenuHelperExtensionFull,
    MenuHelperWindow,
    MenuItemDescription,
    add_menu_items,
    remove_menu_items,
)
from omni.physx.scripts import utils
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics


async def _load_layout(layout_file: str, keep_windows_open=False):
    try:
        from omni.kit.quicklayout import QuickLayout

        # few frames delay to avoid the conflict with the layout of omni.kit.mainwindow
        for i in range(3):
            await omni.kit.app.get_app().next_update_async()
        QuickLayout.load_file(layout_file, keep_windows_open)
        # few frames delay to load the window first
        for i in range(3):
            await omni.kit.app.get_app().next_update_async()

        # make sure viewport 2's camera is "Top View"
        from omni.kit.viewport.utility import get_viewport_from_window_name

        # Get viewport API for a specific named viewport
        viewport_api = get_viewport_from_window_name("Viewport 2")  # Replace with your viewport name
        if viewport_api:
            viewport_api.camera_path = Sdf.Path("/OmniverseKit_Top")

    except Exception as exc:
        pass

        QuickLayout.load_file(layout_file)


class Extension(omni.ext.IExt, MenuHelperExtensionFull):
    EXTENSION_NAME = "Occupancy Map"

    def on_startup(self, ext_id: str):
        # add to menu
        self.menu_startup(
            lambda: OccupancyMapWindow(),
            Extension.EXTENSION_NAME,
            Extension.EXTENSION_NAME,
            "Tools/Robotics",
        )

        # add layout template to Layouts menu
        self._menu_items = [
            MenuItemDescription(name="Occupancy Map Generation", onclick_fn=lambda *_: self._open_layout_fn(ext_id))
        ]
        add_menu_items(self._menu_items, "Layouts")

    def _open_layout_fn(self, ext_id: str):
        ext_manager = omni.kit.app.get_app().get_extension_manager()
        extension_path = ext_manager.get_extension_path(ext_id)
        layout_file = f"{extension_path}/data/omap.json"
        if not os.path.exists(layout_file):
            carb.log_warn(f"Layout file {layout_file} does not exist")
            return

        return asyncio.ensure_future(_load_layout(layout_file))

    def on_shutdown(self):
        # remove layout template from Layouts menu

        remove_menu_items(self._menu_items, "Layouts")
        self.menu_shutdown()


class OccupancyMapWindow(MenuHelperWindow):
    def __init__(self):
        super().__init__(Extension.EXTENSION_NAME, width=600, height=400, focused=True)
        self.deferred_dock_in("Console")

        # Initialize variables
        self._timeline = omni.timeline.get_timeline_interface()
        self._om = _omap.acquire_omap_interface()
        self._layers = omni.kit.usd.layers.get_layers()
        self._filepicker = None
        self._models = {}
        self._stage_open_callback = None

        self.prev_origin = [0, 0]
        self.lower_bound = [-1.00, -1.00]
        self.upper_bound = [1.00, 1.00]

        self.wait_bound_update = False
        self.bound_update_case = 0

        self.units = 0.05  # default assumes 5cm in meters
        if omni.usd.get_context().get_stage():
            self.units = 0.05 / get_stage_units()

        self.build_ui()

    def build_ui(self):
        """
        Build the window UI.
        """
        with self.frame:
            with ui.HStack(spacing=10):
                with ui.VStack(spacing=5, height=0):
                    change_fn = [self.on_update_location, self.on_update_location, self.on_update_location]
                    self._models["origin"] = xyz_builder(label="Origin", on_value_changed_fn=change_fn)

                    self._models["upper_bound"] = xyz_builder(
                        label="Upper Bound",
                        on_value_changed_fn=change_fn,
                        default_val=[self.upper_bound[0], self.upper_bound[1], 0],
                    )
                    self._models["lower_bound"] = xyz_builder(
                        label="Lower Bound",
                        on_value_changed_fn=change_fn,
                        default_val=[self.lower_bound[0], self.lower_bound[1], 0],
                    )

                    self._models["center_bound"] = multi_btn_builder(
                        "Positioning",
                        text=["Center to Selection", "Bound Selection"],
                        on_clicked_fn=[self._on_center_selection, self._on_bound_selection],
                    )

                    self._models["cell_size"] = float_builder(
                        label="Cell Size",
                        default_val=self.units,
                        min=0.001,
                        step=0.001,
                        format="%.3f",
                        tooltip="Size of each pixel in stage units in output occupancy map image",
                    )
                    self._models["cell_size"].add_value_changed_fn(self.on_update_cell_size)
                    self._models["compute"] = multi_btn_builder(
                        "Occupancy Map",
                        text=["Calculate", "Visualize Image"],
                        on_clicked_fn=[self._generate_map, self._generate_image],
                    )

                    self._models["physx_geom"] = cb_builder(
                        "Use PhysX Collision Geometry",
                        tooltip="If True, the current collision approximations are used, if False the original USD meshes are used. for PhysX based lidar use True for RTX lidar use False. Only visible meshes are used",
                        on_clicked_fn=None,
                        default_val=True,
                    )

                    # self.draw_voxel_btn = ui.Button("Draw Voxels", clicked_fn=self._draw_instances)
                    # self.draw_voxel_btn.visible = False

        if self.visible:
            self._models["cell_size"].set_value(self.units)
            self._stage_open_callback = (
                omni.usd.get_context()
                .get_stage_event_stream()
                .create_subscription_to_pop_by_type(int(omni.usd.StageEventType.OPENED), self._stage_open_callback_fn)
            )

    def _stage_open_callback_fn(self, event):
        carb.log_warn(f"New stage opened, setting cell_size to {self.units} to match stage units")
        self._models["cell_size"].set_value(self.units)

    def _on_center_selection(self):
        origin = self.calculate_bounds(True, True)

        self._models["origin"][0].set_value(origin[0])
        self._models["origin"][1].set_value(origin[1])

        self.lower_bound, self.upper_bound = self.calculate_bounds(False, True)
        self.set_bound_value_ui()

    def calculate_bounds(self, origin_calc, stationary_bounds):
        origin_coord = [self._models["origin"][0].get_value_as_float(), self._models["origin"][1].get_value_as_float()]

        if not origin_calc and stationary_bounds:
            lower_bound = [
                self.lower_bound[0] + self.prev_origin[0] - origin_coord[0],
                self.lower_bound[1] + self.prev_origin[1] - origin_coord[1],
            ]

            upper_bound = [
                self.upper_bound[0] + self.prev_origin[0] - origin_coord[0],
                self.upper_bound[1] + self.prev_origin[1] - origin_coord[1],
            ]
            return lower_bound, upper_bound

        selected_prims = omni.usd.get_context().get_selection().get_selected_prim_paths()
        stage = omni.usd.get_context().get_stage()
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), includedPurposes=[UsdGeom.Tokens.default_])
        bbox_cache.Clear()
        total_bounds = Gf.BBox3d()

        if len(selected_prims) > 0:
            for prim_path in selected_prims:
                prim = stage.GetPrimAtPath(prim_path)
                bounds = bbox_cache.ComputeWorldBound(prim)
                total_bounds = Gf.BBox3d.Combine(total_bounds, Gf.BBox3d(bounds.ComputeAlignedRange()))
            range = total_bounds.GetBox()
            mid_point = range.GetMidpoint()
            if origin_calc:
                self.prev_origin = origin_coord
                origin_value = mid_point
                return origin_value

            min_point = range.GetMin()
            max_point = range.GetMax()

            lower_bound = [None] * 2
            upper_bound = [None] * 2

            lower_bound[0] = min_point[0] - origin_coord[0]
            lower_bound[1] = min_point[1] - origin_coord[1]

            upper_bound[0] = max_point[0] - origin_coord[0]
            upper_bound[1] = max_point[1] - origin_coord[1]

            return lower_bound, upper_bound
        else:
            if origin_calc:
                return [0] * 2
        return [0] * 2, [0] * 2

    def set_bound_value_ui(self):
        self.wait_bound_update = True
        self.bound_update_case = 0
        self._models["lower_bound"][0].set_value(self.lower_bound[0])

        # Updating Case every time bound value is updating
        self.bound_update_case += 1

        self._models["lower_bound"][1].set_value(self.lower_bound[1])

        self.bound_update_case += 1

        self._models["upper_bound"][0].set_value(self.upper_bound[0])

        self.bound_update_case += 1

        self._models["upper_bound"][1].set_value(self.upper_bound[1])

        self.wait_bound_update = False

    def _on_bound_selection(self):
        self.lower_bound, self.upper_bound = self.calculate_bounds(False, False)
        self.set_bound_value_ui()

    def on_update_location(self, value):
        if (
            self._models["lower_bound"][0].get_value_as_float() >= self._models["upper_bound"][0].get_value_as_float()
            or self._models["lower_bound"][1].get_value_as_float()
            >= self._models["upper_bound"][1].get_value_as_float()
            or self._models["lower_bound"][2].get_value_as_float() > self._models["upper_bound"][2].get_value_as_float()
        ):
            # carb.log_warn("lower bound is >= upper bound")
            return
        if self.wait_bound_update:
            if self.bound_update_case == 0:
                self.lower_bound[0] = self._models["lower_bound"][0].get_value_as_float()
            elif self.bound_update_case == 1:
                self.lower_bound[1] = self._models["lower_bound"][1].get_value_as_float()
            elif self.bound_update_case == 2:
                self.upper_bound[0] = self._models["upper_bound"][0].get_value_as_float()
            elif self.bound_update_case == 3:
                self.upper_bound[1] = self._models["upper_bound"][1].get_value_as_float()
        else:
            self.lower_bound[0] = self._models["lower_bound"][0].get_value_as_float()
            self.lower_bound[1] = self._models["lower_bound"][1].get_value_as_float()
            self.upper_bound[0] = self._models["upper_bound"][0].get_value_as_float()
            self.upper_bound[1] = self._models["upper_bound"][1].get_value_as_float()

        update_location(
            self._om,
            [
                self._models["origin"][0].get_value_as_float(),
                self._models["origin"][1].get_value_as_float(),
                self._models["origin"][2].get_value_as_float(),
            ],
            [self.lower_bound[0], self.lower_bound[1], self._models["lower_bound"][2].get_value_as_float()],
            [self.upper_bound[0], self.upper_bound[1], self._models["upper_bound"][2].get_value_as_float()],
        )

    def on_update_cell_size(self, value):
        self._om.set_cell_size(self._models["cell_size"].get_value_as_float())

    def _draw_instances(self):

        instancePath = "/occupancyMap/occupiedInstances"
        cubePath = "/occupancyMap/occupiedCube"
        pos_list = self._om.get_occupied_positions()
        scale = self._models["cell_size"].get_value_as_float() * 0.5
        color = (0.0, 1.0, 1.0)
        stage = omni.usd.get_context().get_stage()
        if stage.GetPrimAtPath(instancePath):
            stage.RemovePrim(instancePath)
        point_instancer = UsdGeom.PointInstancer(stage.DefinePrim(instancePath, "PointInstancer"))
        positions_attr = point_instancer.CreatePositionsAttr()
        if stage.GetPrimAtPath(cubePath):
            stage.RemovePrim(cubePath)
        occupiedCube = UsdGeom.Cube(stage.DefinePrim(cubePath, "Cube"))
        occupiedCube.AddScaleOp().Set(Gf.Vec3d(1, 1, 1) * scale)
        occupiedCube.CreateDisplayColorPrimvar().Set([color])

        point_instancer.CreatePrototypesRel().SetTargets([occupiedCube.GetPath()])
        proto_indices_attr = point_instancer.CreateProtoIndicesAttr()
        print("total points drawn: ", len(pos_list))
        positions_attr.Set(pos_list)
        proto_indices_attr.Set([0] * len(pos_list))

    def _generate_map(self):
        if (
            self._models["lower_bound"][0].get_value_as_float() >= self._models["upper_bound"][0].get_value_as_float()
            or self._models["lower_bound"][1].get_value_as_float()
            >= self._models["upper_bound"][1].get_value_as_float()
            or self._models["lower_bound"][2].get_value_as_float() > self._models["upper_bound"][2].get_value_as_float()
        ):
            carb.log_warn("lower bound is >= upper bound, cannot calculate map")
            return

        self.on_update_location(0)
        self.on_update_cell_size(0)

        async def generate_task():
            self._timeline.stop()
            await omni.kit.app.get_app().next_update_async()
            if not self._models["physx_geom"].get_value_as_bool():
                layer = Sdf.Layer.CreateAnonymous("anon_occupancy_map")
                stage = omni.usd.get_context().get_stage()
                session = stage.GetSessionLayer()
                session.subLayerPaths.append(layer.identifier)
                with Usd.EditContext(stage, layer):
                    with Sdf.ChangeBlock():
                        for prim in stage.Traverse():
                            if prim.HasAPI(UsdPhysics.CollisionAPI) and prim.HasAPI(UsdPhysics.RigidBodyAPI):
                                utils.removePhysics(prim)
                    await omni.kit.app.get_app().next_update_async()
                    with Sdf.ChangeBlock():
                        for prim in stage.Traverse():
                            # Skip invisible
                            imageable = UsdGeom.Imageable(prim)
                            if imageable:
                                visibility = imageable.ComputeVisibility(Usd.TimeCode.Default())
                                if visibility == UsdGeom.Tokens.invisible:
                                    continue
                            # Skip meshes with no points
                            if prim.IsA(UsdGeom.Mesh):
                                usdMesh = UsdGeom.Mesh(prim)
                                attr = usdMesh.GetPointsAttr().Get()
                                if attr is None or len(attr) == 0:
                                    continue
                            if prim.HasAPI(UsdPhysics.CollisionAPI):
                                if prim.HasAPI(UsdPhysics.MeshCollisionAPI):
                                    collision_api = UsdPhysics.MeshCollisionAPI(prim)
                                    approx = collision_api.GetApproximationAttr().Get()
                                    if approx == "none":
                                        continue
                                if prim.IsA(UsdGeom.Gprim):
                                    if prim.IsInstanceable():
                                        UsdPhysics.CollisionAPI.Apply(prim)
                                        UsdPhysics.MeshCollisionAPI.Apply(prim)
                                    else:
                                        # Skip if we have errors here
                                        try:
                                            utils.setCollider(prim, "none")
                                        except Exception as e:
                                            continue
                            elif prim.IsA(UsdGeom.Xformable) and prim.IsInstanceable():
                                UsdPhysics.CollisionAPI.Apply(prim)
                                UsdPhysics.MeshCollisionAPI.Apply(prim)
                            elif prim.IsA(UsdGeom.Gprim):
                                UsdPhysics.CollisionAPI.Apply(prim)
                                UsdPhysics.MeshCollisionAPI.Apply(prim)

                self._timeline.play()
                await omni.kit.app.get_app().next_update_async()
                self._om.generate()
                await omni.kit.app.get_app().next_update_async()
                self._timeline.stop()
                session.subLayerPaths.remove(layer.identifier)
                layer = None
            else:
                self._timeline.play()
                await omni.kit.app.get_app().next_update_async()
                self._om.generate()
                await omni.kit.app.get_app().next_update_async()
                self._timeline.stop()

        asyncio.ensure_future(generate_task())
        # self.generate_image_btn.visible = True
        # self.draw_voxel_btn.visible = True

    def _fill_image(self):
        dims = self._om.get_dimensions()
        scale = self._models["cell_size"].get_value_as_float()
        if scale <= 0:
            carb.log_warn("Cell size is less than or equal to 0. A value of 0.01 meters will be used instead.")
            scale = 0.01
        # Clockwise rotation
        rotate_image_angle = 180
        current_image_rotation_index = self._models["rotation"].get_item_value_model().as_int
        if current_image_rotation_index == 0:  # 180 degrees
            top_left, top_right, bottom_left, bottom_right, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = 180
        elif current_image_rotation_index == 1:  # 0 degrees
            top_right, bottom_right, top_left, bottom_left, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = 0
        elif current_image_rotation_index == 2:  # -90 degrees
            top_right, bottom_right, top_left, bottom_left, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = -90
        elif current_image_rotation_index == 3:  # 90 degrees
            bottom_left, top_left, bottom_right, top_right, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = 90

        rotate_image_angle = 180
        current_image_rotation_index = self._models["rotation"].get_item_value_model().as_int
        if current_image_rotation_index == 0:  # 180 degrees
            bottom_right, bottom_left, top_right, top_left, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = 180
        elif current_image_rotation_index == 1:  # 0 degrees
            top_left, top_right, bottom_left, bottom_right, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = 0
        elif current_image_rotation_index == 2:  # -90 degrees
            top_right, bottom_right, top_left, bottom_left, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = -90
        elif current_image_rotation_index == 3:  # 90 degrees
            bottom_left, top_left, bottom_right, top_right, image_coords = compute_coordinates(self._om, scale)
            rotate_image_angle = 90

        occupied_col = []
        for item in self._models["occupied_color"].get_item_children():
            component = self._models["occupied_color"].get_item_value_model(item)
            occupied_col.append(int(component.get_value_as_float() * 255))

        freespace_col = []
        for item in self._models["freespace_color"].get_item_children():
            component = self._models["freespace_color"].get_item_value_model(item)
            freespace_col.append(int(component.get_value_as_float() * 255))

        unknown_col = []
        for item in self._models["unknown_color"].get_item_children():
            component = self._models["unknown_color"].get_item_value_model(item)
            unknown_col.append(int(component.get_value_as_float() * 255))

        self._image = generate_image(self._om, occupied_col, unknown_col, freespace_col)

        from PIL import Image

        self._im = Image.frombytes("RGBA", (dims.x, dims.y), bytes(self._image))
        self._im = self._im.rotate(-rotate_image_angle, expand=True)
        self._image = list(self._im.tobytes())

        image_width = self._im.width
        image_height = self._im.height

        size = [0, 0, 0]

        size[0] = image_width * scale
        size[1] = image_height * scale

        self._rgb_byte_provider.set_bytes_data(self._image, [int(size[0] / scale), int(size[1] / scale)])
        self._image_frame.rebuild()

        image_details_text = f"Top Left: {top_left}\t\t Top Right: {top_right}\n Bottom Left: {bottom_left}\t\t Bottom Right: {bottom_right}"
        image_details_text += f"\nCoordinates of top left of image (pixel 0,0) as origin, + X down, + Y right:\n{float(image_coords[0][0]), float(image_coords[1][0])}"
        image_details_text += f"\nImage size in pixels: {int(size[0] / scale)}, {int(size[1] / scale)}"

        scale_to_meters = 1.0 / get_stage_units()

        stage = omni.usd.get_context().get_stage()
        root = stage.GetRootLayer()
        default_image_name = root.GetDisplayName().rsplit(".", 1)[0]
        default_image_name += ".png"

        ros_yaml_file_text = "image: " + default_image_name
        ros_yaml_file_text += f"\nresolution: {float( scale/ scale_to_meters)}"
        ros_yaml_file_text += (
            f"\norigin: [{float(bottom_left[0]/scale_to_meters)}, {float(bottom_left[1]/scale_to_meters)}, 0.0000]"
        )
        ros_yaml_file_text += "\nnegate: 0"
        ros_yaml_file_text += f"\noccupied_thresh: {0.65}"
        ros_yaml_file_text += "\nfree_thresh: 0.196"

        current_data_output_index = self._models["config_type"].get_item_value_model().as_int
        if current_data_output_index == 0:
            self._models["config_data"].set_value(ros_yaml_file_text)
        elif current_data_output_index == 1:
            self._models["config_data"].set_value(image_details_text)

    def save_image(self, file, folder):
        from PIL import Image

        image_width = self._im.width
        image_height = self._im.height
        file = file if file[-4:].lower() == ".png" else "{}.png".format(file)
        im = Image.frombytes("RGBA", (image_width, image_height), bytes(self._image))
        print("Saving occupancy map image to", folder + "/" + file)
        im.save(folder + "/" + file)
        self._filepicker.hide()

    def save_file(self):
        from omni.kit.widget.filebrowser import FileBrowserItem
        from omni.kit.window.filepicker import FilePickerDialog

        def _on_filter_png_files(item: FileBrowserItem) -> bool:
            """Callback to filter the choices of file names in the open or save dialog"""
            if not item or item.is_folder:
                return True
            # Show only files with listed extensions
            return os.path.splitext(item.path)[1] == ".png"

        self._filepicker = None
        self._filepicker = FilePickerDialog(
            "Save .png image",
            allow_multi_selection=False,
            apply_button_label="Save",
            click_apply_handler=self.save_image,
            item_filter_options=[".png Files (*.png, *.PNG)"],
            item_filter_fn=_on_filter_png_files,
        )

    def rebuild_frame(self):
        if self._image is not None:
            with ui.VStack():
                omni.ui.ImageWithProvider(self._rgb_byte_provider)
                ui.Button("Save Image", clicked_fn=self.save_file, height=0)

    def _generate_image(self):
        self._image = None
        # check to make sure image has data first
        dims = self._om.get_dimensions()
        if dims.x == 0 or dims.y == 0:
            carb.log_warn(
                "Occupancy map is empty, press CALCULATE first and make sure there is collision geometry in the mapping bounds"
            )
            return
        self._rgb_byte_provider = omni.ui.ByteImageProvider()
        self.visualize_window = omni.ui.Window("Visualization", width=500, height=600)
        with self.visualize_window.frame:
            with ui.VStack(spacing=5):
                with ui.VStack(height=0, spacing=5):
                    kwargs = {"label": "Occupied Color", "default_val": [0, 0, 0, 1]}
                    self._models["occupied_color"] = color_picker_builder(**kwargs)
                    kwargs = {"label": "Freespace Color", "default_val": [1, 1, 1, 1]}
                    self._models["freespace_color"] = color_picker_builder(**kwargs)
                    kwargs = {"label": "Unknown Color", "default_val": [0.5, 0.5, 0.5, 1]}
                    self._models["unknown_color"] = color_picker_builder(**kwargs)
                    self._models["rotation"] = dropdown_builder(
                        label="Rotate Image",
                        items=["180", "0", "-90", "90"],
                        tooltip="Clockwise rotation of image in degrees",
                    )
                    self._models["config_type"] = dropdown_builder(
                        label="Coordinate Type",
                        items=["ROS Occupancy Map Parameters File (YAML)", "Coordinates in Stage Space"],
                        tooltip="Type of config output generated",
                    )
                    self._models["generate"] = btn_builder(
                        label="Occupancy map", text="Re-Generate Image", on_clicked_fn=self._fill_image
                    )
                    self._models["config_data"] = ui.StringField(height=100, multiline=True).model
                self._image_frame = ui.Frame()
                self._image_frame.set_build_fn(self.rebuild_frame)
        # generate image imadeately when this window appears
        self._fill_image()

    def destroy(self):
        """
        overwriting the destroy method to clean up the window
        #"""
        self._stage_open_callback = None
        # Initialize variables
        self._timeline = None
        _omap.release_omap_interface(self._om)
        self._om = None
        self._layers = None
        if self._filepicker is not None:
            self._filepicker.hide()
            self._filepicker = None
        self._models = {}
        self._image = None

        super().destroy()
        gc.collect()
