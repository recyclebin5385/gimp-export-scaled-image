#!/usr/bin/env python3

# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 recyclebin5385

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gio", "2.0") 
from gi.repository import Gimp, GObject, GLib, GimpUi, Gio
import os
import sys
import re
from pathlib import Path
from string import Template

EXT_TYPE_DICT = {
    ".jpg": "jpeg"
}

plug_in_binary = "export-scaled-image"
plug_in_proc = "plug-in-recyclebin5385-" + plug_in_binary

class ExportScaledImage(Gimp.PlugIn):
    def do_query_procedures(self):
        return [ plug_in_proc ]

    def do_create_procedure(self, name):
        proc = None

        if name == plug_in_proc:
            proc = Gimp.ImageProcedure.new(
                self,
                name,
                Gimp.PDBProcType.PLUGIN,
                self.run,
                None
            )

            proc.set_menu_label("_Export scaled image...")
            proc.add_menu_path("<Image>/File")
            proc.set_attribution("recyclebin5385", "recyclebin5385", "2026")
            proc.set_image_types("*")
            proc.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.NO_DRAWABLES)

            proc.add_string_argument(
                "dest_path",
                "Exported file path",
                "Path to the exported image file.\n" +
                "The variables ${current_dir}, ${parent_dir} and ${basedir} can be used.\n" +
                "The file format is automatically determined from the file extension.",
                "${parent_dir}" + os.sep + "scaled" + os.sep + "${basename}.jpg",
                GObject.ParamFlags.READWRITE
            )
            proc.add_int_argument(
                "dest_size",
                "Exported image size",
                "The size of the exported image (the larger of width or height).\n" +
                "The aspect ratio will be preserved.",
                1,
                10000,
                300,
                GObject.ParamFlags.READWRITE
            )

        return proc

    def run(self, procedure, run_mode, image, drawables, config, data):
        if run_mode == Gimp.RunMode.INTERACTIVE:

            # show config dialog

            GimpUi.init(plug_in_binary)

            dialog = GimpUi.ProcedureDialog.new(procedure, config, "Export Scaled Image")
            dialog.fill(["dest_path", "dest_size"])
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
            else:
                dialog.destroy()

        # get config values

        dest_path = config.get_property("dest_path")
        dest_size = config.get_property("dest_size")

        # get destination file path

        src_file = image.get_file()
        if src_file is None:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error()
            )

        var_mapping = {
            "current_dir": os.getcwd(),
            "parent_dir": src_file.get_parent().get_path(),
            "basename": Path(src_file.get_basename()).stem
        }

        parsed_dest_path = Template(dest_path).substitute(var_mapping)
        Gimp.message(f"File will be exported to '{parsed_dest_path}'.")

        dest_ext = os.path.splitext(parsed_dest_path)[1]
        dest_type = EXT_TYPE_DICT.get(dest_ext.lower()) or dest_ext.removeprefix(".").lower()

        # find exporting procedure matching file name extension

        pdb = Gimp.get_pdb()
        procedure = pdb.lookup_procedure(f"file-{dest_type}-export")        
        if not procedure:
            Gimp.message(f"No exporting procedure found for extension: {dest_ext}")
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error()
            )

        # create scaled image 
        
        src_size = max(image.get_width(), image.get_height())
        dest_width = image.get_width() * dest_size // src_size
        dest_height = image.get_height() * dest_size // src_size
        
        tmp_image = image.duplicate()
        try:
            tmp_image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
            old_interpolation = Gimp.context_get_interpolation()
            Gimp.context_set_interpolation(Gimp.InterpolationType.LOHALO)
            try:
                tmp_image.scale(dest_width, dest_height)
            finally:
                Gimp.context_set_interpolation(old_interpolation)

            # execute exporting procedure

            os.makedirs(Path(parsed_dest_path).parent, exist_ok = True)

            config = procedure.create_config()
            config.set_property("run-mode", Gimp.RunMode.INTERACTIVE)
            config.set_property("image", tmp_image)
            config.set_property("file", Gio.File.new_for_path(parsed_dest_path))
            procedure.run(config)
        finally:
            tmp_image.delete

        Gimp.displays_flush()

        return procedure.new_return_values(
            Gimp.PDBStatusType.SUCCESS,
            GLib.Error()
        )

Gimp.main(ExportScaledImage.__gtype__, sys.argv)
