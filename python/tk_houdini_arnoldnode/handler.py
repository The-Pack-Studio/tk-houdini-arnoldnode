# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# built-ins
import os
import sys
import re

# houdini
import hou

# toolkit
import sgtk


class TkArnoldNodeHandler(object):
    """Handle Tk Arnold node operations and callbacks."""

    ############################################################################
    # Class data

    # mostly a collection of strings that are reused throughout the handler.  

    HOU_ARNOLD_NODE_TYPE = "ifd"
    """Houdini type for arnold node."""

    NODE_OUTPUT_PATH_PARM = "sgtk_ar_filename"

    TK_EXTRA_PLANE_COUNT_PARM = "ar_aovs"
    """Parameter that stores the number of aov planes."""

    TK_EXTRA_PLANE_TEMPLATE_MAPPING = {
        "sgtk_ar_aov_separate_file#": "output_extra_plane_template"
    }
    """Maps additional plane parameter names to output template names"""

    TK_EXTRA_PLANES_NAME = "ar_aov_label%s"
    """Placeholder used to format extra plane names"""

    TK_INIT_PARM_NAME = "sgtk_initialized"
    """Parameter used to store whether a tk arnold node has been initialized."""

    TK_HIP_PATH_PARM_NAME = "sgtk_hip_path"
    """Holds cached path to the hip file."""

    TK_ARNOLD_NODE_TYPE = "sgtk_arnold"
    """The clase of node as defined in Houdini for the Arnold nodes."""

    TK_OUTPUT_PROFILE_PARM = "sgtk_output_profile" 
    """The name of the parameter that stores the current output profile."""

    TK_OUTPUT_PROFILE_NAME_KEY = "tk_output_profile_name"
    """The key in the user data that stores the output profile name."""

    TK_RENDER_TEMPLATE_MAPPING = {
        "sgtk_ass_diskfile": "output_ifd_template",
        "sgtk_ar_filename": "output_render_template",
    }
    """Mapping between tk arnold parms and corresponding render templates."""

    TK_RESET_PARM_NAMES = [
        "soho_compression",
        "soho_mkpath",
        "vm_device",
        "vm_image_exr_compression",
        "vm_image_jpeg_quality",
        "vm_image_tiff_compression",
    ]
    """The default parameters to reset when the profile changes."""

    TK_DEFAULT_UPDATE_PARM_MAPPING = {     
        "sgtk_ass_diskfile": "ar_ass_file",
        "sgtk_ar_picture": "ar_picture",
    }
    """Map tk parms to arnold node parms."""

    ############################################################################
    # Class methods

    @classmethod
    def convert_back_to_tk_arnold_nodes(cls, app):
        """Convert Arnold nodes back to Toolkit Arnold nodes.

        :param app: The calling Toolkit Application

        Note: only converts nodes that had previously been Toolkit Arnold
        nodes.

        """

        # get all instances of the built-in arnold nodes
        arnold_nodes = hou.nodeType(
            hou.ropNodeTypeCategory(), cls.HOU_ARNOLD_NODE_TYPE).instances()

        if not arnold_nodes:
            app.log_debug("No Arnold Nodes found for conversion.")
            return
        
        # iterate over all the arnold nodes and attempt to convert them
        for arnold_node in arnold_nodes:

            # get the user data dictionary stored on the node
            user_dict = arnold_node.userDataDict()

            # get the output_profile from the dictionary
            tk_output_profile_name = user_dict.get(
                cls.TK_OUTPUT_PROFILE_NAME_KEY)

            if not tk_output_profile_name:
                app.log_warning(
                    "Arnold node '%s' does not have an output profile name. "
                    "Can't convert to Tk Arnold node. Continuing." %
                    (arnold_node.name(),)
                )
                continue

            # create new Shotgun Write node:
            tk_node_type = TkArnoldNodeHandler.TK_ARNOLD_NODE_TYPE
            tk_arnold_node = arnold_node.parent().createNode(tk_node_type)

            # find the index of the stored name on the new tk arnold node
            # and set that item in the menu.
            try:
                output_profile_parm = tk_arnold_node.parm(
                    TkArnoldNodeHandler.TK_OUTPUT_PROFILE_PARM)
                output_profile_index = output_profile_parm.menuLabels().index(
                    tk_output_profile_name)
                output_profile_parm.set(output_profile_index)
            except ValueError:
                app.log_warning("No output profile found named: %s" % 
                    (tk_output_profile_name,))

            # copy over all parameter values except the output path 
            _copy_parm_values(arnold_node, tk_arnold_node, excludes=[])

            # explicitly copy AOV settings to the new tk arnold node
            plane_numbers = _get_extra_plane_numbers(arnold_node)
            for plane_number in plane_numbers:
                plane_parm_name = cls.TK_EXTRA_PLANES_NAME % (plane_number,)
                aov_name = user_dict.get(plane_parm_name)
                tk_arnold_node.parm(plane_parm_name).set(aov_name)

            # copy the inputs and move the outputs
            _copy_inputs(arnold_node, tk_arnold_node)
            _move_outputs(arnold_node, tk_arnold_node)

            # remember the name and position of the original arnold node
            arnold_node_name = arnold_node.name()
            arnold_node_pos = arnold_node.position()

            # destroy the original arnold node
            arnold_node.destroy()

            # name and reposition the new, regular arnold node to match the
            # original
            tk_arnold_node.setName(arnold_node_name)
            tk_arnold_node.setPosition(arnold_node_pos)

            app.log_debug("Converted: Arnold node '%s' to TK Arnold node."
                % (arnold_node_name,))


    @classmethod
    def convert_to_regular_arnold_nodes(cls, app):
        """Convert Toolkit Arnold nodes to regular Arnold nodes.

        :param app: The calling Toolkit Application

        """

        # get all instances of tk arnold nodes
        tk_node_type = TkArnoldNodeHandler.TK_ARNOLD_NODE_TYPE
        tk_arnold_nodes = hou.nodeType(
            hou.ropNodeTypeCategory(), tk_node_type).instances()

        if not tk_arnold_nodes:
            app.log_debug("No Toolkit Arnold Nodes found for conversion.")
            return

        for tk_arnold_node in tk_arnold_nodes:

            # create a new, regular Arnold node
            arnold_node = tk_arnold_node.parent().createNode(
                cls.HOU_ARNOLD_NODE_TYPE)

            # copy across knob values
            exclude_parms = [parm for parm in tk_arnold_node.parms() 
                if parm.name().startswith("sgtk_")]
            _copy_parm_values(tk_arnold_node, arnold_node,
                excludes=exclude_parms)

            # store the arnold output profile name in the user data so that we
            # can retrieve it later.
            output_profile_parm = tk_arnold_node.parm(
                cls.TK_OUTPUT_PROFILE_PARM)
            tk_output_profile_name = \
                output_profile_parm.menuLabels()[output_profile_parm.eval()]
            arnold_node.setUserData(cls.TK_OUTPUT_PROFILE_NAME_KEY, 
                tk_output_profile_name)

            # store AOV info on the new node
            plane_numbers = _get_extra_plane_numbers(tk_arnold_node)
            for plane_number in plane_numbers:
                plane_parm_name = cls.TK_EXTRA_PLANES_NAME % (plane_number,)
                arnold_node.setUserData(plane_parm_name,
                    tk_arnold_node.parm(plane_parm_name).eval())

            # copy the inputs and move the outputs
            _copy_inputs(tk_arnold_node, arnold_node)
            _move_outputs(tk_arnold_node, arnold_node)

            # remember the name and position of the original tk arnold node
            tk_arnold_node_name = tk_arnold_node.name()
            tk_arnold_node_pos = tk_arnold_node.position()

            # destroy the original tk arnold node
            tk_arnold_node.destroy()

            # name and reposition the new, regular arnold node to match the
            # original
            arnold_node.setName(tk_arnold_node_name)
            arnold_node.setPosition(tk_arnold_node_pos)

            app.log_debug("Converted: Tk Arnold node '%s' to Arnold node."
                % (tk_arnold_node_name,))

    @classmethod
    def get_all_tk_arnold_nodes(cls):
        """
        Returns a list of all tk-houdini-arnoldnode instances in the current
        session.
        """

        # get all instances of tk arnold nodes
        tk_node_type = TkArnoldNodeHandler.TK_ARNOLD_NODE_TYPE
        return hou.nodeType(hou.ropNodeTypeCategory(), tk_node_type).instances()

    @classmethod
    def get_output_path(cls, node):
        """
        Returns the evaluated output path for the supplied node.
        """

        output_parm = node.parm(cls.NODE_OUTPUT_PATH_PARM)
        return output_parm.eval()

    ############################################################################
    # Instance methods

    def __init__(self, app):
        """Initialize the handler.
        
        :params app: The application instance. 
        
        """

        # keep a reference to the app for easy access to templates, settings,
        # logging methods, tank, context, etc.
        self._app = app

        # get and cache the list of profiles defined in the settings
        self._output_profiles = {}
        for output_profile in self._app.get_setting("output_profiles", []):
            output_profile_name = output_profile["name"]

            if output_profile_name in self._output_profiles:
                self._app.log_warning(
                    "Found multiple output profiles named '%s' for the "
                    "Tk Arnold node! Only the first one will be available." %
                    (output_profile_name,)
                )
                continue

            self._output_profiles[output_profile_name] = output_profile
            self._app.log_debug("Caching arnold output profile: '%s'" % 
                (output_profile_name,))


    ############################################################################
    # methods and callbacks executed via the OTL

    def copy_path_to_clipboard(self):
        """Copies the evaluated render path template to the clipboard."""

        render_path = self._get_render_path(hou.pwd())

        # use Qt to copy the path to the clipboard:
        from sgtk.platform.qt import QtGui
        QtGui.QApplication.clipboard().setText(render_path)

        self._app.log_debug(
            "Copied render path to clipboard: %s" % (render_path,))

    def get_output_profile_menu_labels(self):
        """Returns labels for all tk-houdini-arnoldnode output profiles."""

        menu_labels = []
        for count, output_profile_name in enumerate(self._output_profiles):
            menu_labels.extend([count, output_profile_name])

        return menu_labels


    def get_output_path_menu(self, node=None):
        """Returns a list of output path menu items for the current node.
        
        :param hou.Node node: The node being acted upon.

        :return: The menu of the form [menu_id, display, menu_id, display, ...]
        :rtype: list of str
        
        """

        if not None:
            node = hou.pwd()

        # is this the first time this has been created?
        is_first_run = (node.parm(self.TK_INIT_PARM_NAME).eval() == "True")
        if is_first_run:
            # set it to false for subsequent calls
            node.parm(is_first_run).set("False")

        # see if the hip file has changed
        hip_path_changed = (
            hou.hipFile.path() != node.parm(self.TK_HIP_PATH_PARM_NAME).eval())

        if is_first_run or hip_path_changed:
            # make sure node is in default state.
            self.reset_render_path(node)

            # cache current hip file path to compare against later
            node.parm(self.TK_HIP_PATH_PARM_NAME).set(hou.hipFile.path())

        # get path from hidden parameter which acts like a cache.
        path = node.parm(self.NODE_OUTPUT_PATH_PARM).unexpandedString()

        # Build the menu
        menu = ["sgtk", path,
                "ip", "mplay (interactive)",
                "md", "mplay (non-interactive)"]

        return menu


    def reset_render_path(self, node=None):
        """Reset the render path of the specified node. 

        :param hou.Node node: The node being acted upon.
        
        This will force the render path to be updated based on the current
        script path and configuraton.
        """

        if not node:
            node = hou.pwd()

        # Checks to see if the supplied node is being copied. Houdini renames
        # the node by prepending original0_ to the original node when copying.
        if node.name().startswith("original0"):
            return

        for (parm_name, template_name) in self.TK_RENDER_TEMPLATE_MAPPING.items():
            self._compute_and_set(node, parm_name, template_name)

        # Extra Image Planes / AOVs
        plane_numbers = _get_extra_plane_numbers(node)
        for plane_number in plane_numbers:
            usefile_parm = node.parm("ar_aov_separate%s" % (plane_number,)) 

            # only compute the template path if plane is using a different file
            if usefile_parm.eval():
                for (parm_name, template_name) in \
                    self.TK_EXTRA_PLANE_TEMPLATE_MAPPING.items():
                    parm_name = parm_name.replace("#", str(plane_number))
                    aov_name = node.parm(
                        self.TK_EXTRA_PLANES_NAME % (plane_number,)).eval()
                    self._compute_and_set(node, parm_name, template_name,
                        aov_name)

        # set the output paths
        path = node.parm(self.NODE_OUTPUT_PATH_PARM).unexpandedString()
        node.parm("sgtk_ar_picture").set(path)
        node.parm("ar_picture").set(path)

        self.update_parms(node)


    def set_profile(self, node=None, reset=False):
        """Apply the selected profile in the session.
        
        :param hou.Node node: The node being acted upon.
        :param bool reset: When True, reset predefined param to defaults.
            Includes TK_RESET_PARM_NAMES parms.
        
        """

        if not node:
            node = hou.pwd()

        output_profile = self._get_output_profile(node)

        self._app.log_debug("Applying tk arnold node profile: %s" % 
            (output_profile["name"],))

        # reset some parameters if need be
        if reset:
            for parm_name in self.TK_RESET_PARM_NAMES:
                parm = node.parm(parm_name)
                if parm:
                    parm.revertToDefaults()

            node.setColor(hou.Color([.8, .8, .8]))

        # apply the supplied settings to the node
        settings = output_profile["settings"]
        if settings:
            self._app.log_debug("Populating format settings: %s" % (settings,))
            node.setParms(settings)

        self.reset_render_path(node)


    def show_in_fs(self):
        """Open a file browser showing the render path of the current node."""

        # retrieve the calling node
        current_node = hou.pwd()
        if not current_node:
            return

        render_dir = None

        # first, try to just use the current cached path:
        render_path = self._get_render_path(current_node)

        if render_path:
            # the above method returns houdini style slashes, so ensure these
            # are pointing correctly
            render_path = render_path.replace("/", os.path.sep)

            dir_name = os.path.dirname(render_path)
            if os.path.exists(dir_name):
                render_dir = dir_name

        if not render_dir:
            # render directory doesn't exist so try using location
            # of rendered frames instead:
            rendered_files = self._get_rendered_files(current_node)

            if not rendered_files:
                msg = ("Unable to find rendered files for node '%s'." 
                       % (current_node,))
                self._app.log_error(msg)
                hou.ui.displayMessage(msg)
                return
            else:
                render_dir = os.path.dirname(rendered_files[0])

        # if we have a valid render path then show it:
        if render_dir:
            # TODO: move to utility method in core
            system = sys.platform

            # run the app
            if system == "linux2":
                cmd = "xdg-open \"%s\"" % render_dir
            elif system == "darwin":
                cmd = "open '%s'" % render_dir
            elif system == "win32":
                cmd = "cmd.exe /C start \"Folder\" \"%s\"" % render_dir
            else:
                msg = "Platform '%s' is not supported." % (system,)
                self._app.log_error(msg)
                hou.ui.displayMessage(msg)

            self._app.log_debug("Executing command:\n '%s'" % (cmd,))
            exit_code = os.system(cmd)
            if exit_code != 0:
                msg = "Failed to launch '%s'!" % (cmd,)
                hou.ui.displayMessage(msg)

    def setup_node(self, node):
        """Setup newly created node with default name, profile, settings.
        
        :param hou.Node node: The node being acted upon.
        
        """
        
        default_name = self._app.get_setting("default_node_name")
        node.setName(default_name, unique_name=True)

        # apply the default profile
        self.set_profile(node, reset=True)

        # make sure the render paths are in default state
        self.reset_render_path(node)

        try:
            self._app.log_metric("Create", log_version=True)
        except:
            # ingore any errors. ex: metrics logging not supported
            pass

    def update_parms(self, node=None):
        """Update a set of predefined parameters as the render path changes.
        
        :param hou.Node node: The node being acted upon.
        
        
        """

        if not node:
            node = hou.pwd()

        # copies the value of one parm to another
        copy_parm = lambda p1, p2: \
            node.parm(p2).set(node.parm(p1).unexpandedString())

        # copy the default udpate parms
        for parm1, parm2 in self.TK_DEFAULT_UPDATE_PARM_MAPPING.items():
            copy_parm(parm1, parm2)

        # handle additional planes
        plane_numbers = _get_extra_plane_numbers(node)
        for plane_number in plane_numbers:
            parm1 = "sgtk_ar_aov_separate_file" + str(plane_number)
            parm2 = "ar_aov_separate_file" + str(plane_number)
            copy_parm(parm1, parm2)
    
    def use_file_plane(self, **kwargs):
        """Callback for "Different File" checkbox on every Extra Image Plane.

        :param hou.Node node: The node being acted upon.
        :param hou.Parm parm: The checkbox parm for turning the option on/off.
        
        Sets the AOV Name to Channel Name or VEX Variable.  Resets the render
        paths to update the path for this AOV.  Sets the Label to "Disabled."
        when it is unchecked.

        """

        node = kwargs["node"]
        parm = kwargs["parm"]
    
        # replace the parm basename with nothing, leaving the plane number
        plane_number = re.findall(r'\d+', parm.name())[-1]
        
        if node.parm('ar_aov_separate{}'.format(plane_number)).eval():
            self.reset_render_path(node)
        else:
            path_parm = node.parm("sgtk_ar_aov_separate_file%s" % (plane_number,))
            path_parm.lock(False)
            path_parm.set("Disabled")
            path_parm.lock(True)


    ############################################################################
    # Private methods

    def _compute_and_set(self, node, parm_name, template_name, aov_name=None):
        """Compute and set and output path for the supplied parm.
        
        :param hou.Node node: The node being acted upon.
        :param str parm_name: The name of the parameter to set.
        :param str template_name: The template to compute as the output path.
        :param str aov_name: Optional AOV name used during comput of path.
        
        """

        try:
            path = self._compute_output_path(node, template_name, aov_name)
        except sgtk.TankError as err:
            self._app.log_warning("%s: %s" % (node.name(), err))
            path = "ERROR: %s" % (err,)

        # Unlock, set, lock
        node.parm(parm_name).lock(False)
        node.parm(parm_name).set(path)
        node.parm(parm_name).lock(True)


    def _compute_output_path(self, node, template_name, aov_name=None):
        """Compute output path based on current work file and render template.

        :param hou.Node node: The node being acted upon.
        :param str template_name: The name of template to compute a path for.
        :param str aov_name: Optional AOV name used to compute the path.

        """

        # Get relevant fields from the scene filename and contents
        work_file_fields = self._get_hipfile_fields()

        if not work_file_fields:
            msg = "This Houdini file is not a Shotgun Toolkit work file!"
            raise sgtk.TankError(msg)

        output_profile = self._get_output_profile(node)

        # Get the render template from the app
        output_template = self._app.get_template_by_name(
            output_profile[template_name])

        # create fields dict with all the metadata
        fields = {
            "name": work_file_fields.get("name", None),
            "node": node.name(),
            "renderpass": node.name(),
            "SEQ": "FORMAT: $F",
            "version": work_file_fields.get("version", None),
        } 

        # use %V - full view printout as default for the eye field
        fields["eye"] = "%V"

        if aov_name:
            fields["aov_name"] = aov_name

        fields.update(self._app.context.as_template_fields(output_template))

        path = output_template.apply_fields(fields)
        path = path.replace(os.path.sep, "/")

        return path


    def _get_output_profile(self, node=None):
        """Get the current output profile.
        
        :param hou.Node node: The node being acted upon.
        
        """

        if not node:
            node = hou.pwd()

        output_profile_parm = node.parm(self.TK_OUTPUT_PROFILE_PARM)
        output_profile_name = \
            output_profile_parm.menuLabels()[output_profile_parm.eval()]
        return self._output_profiles[output_profile_name]


    def _get_hipfile_fields(self):
        """Extract fields from current Houdini file using workfile template."""

        current_file_path = hou.hipFile.path()

        work_fields = {}
        work_file_template = self._app.get_template("work_file_template")
        if (work_file_template and 
            work_file_template.validate(current_file_path)):
            work_fields = work_file_template.get_fields(current_file_path)

        return work_fields


    def _get_render_path(self, node):
        """Get render path from current item in the output path parm menu.

        :param hou.Node node: The node being acted upon.

        """

        output_parm = node.parm(self.NODE_OUTPUT_PATH_PARM)
        return output_parm.unexpandedString()

    
    def _get_rendered_files(self, node):
        """Returns the files on disk associated with this node.

        :param hou.Node node: The node being acted upon.

        """

        file_name = self._get_render_path(node)
        output_profile = self._get_output_profile(node)

        # get the output cache template for the current profile
        output_render_template = self._app.get_template_by_name(
            output_profile["output_render_template"])

        if not output_render_template.validate(file_name):
            msg = ("Unable to validate files on disk for node %s."
                   "The path '%s' is not recognized by Shotgun."
                   % (node.name(), file_name))
            self._app.log_error(msg)
            return []
            
        fields = output_render_template.get_fields(file_name)

        # get the actual file paths based on the template. Ignore any sequence
        # or eye fields
        return self._app.tank.paths_from_template(
            output_render_template, fields, ["SEQ", "eye"])


################################################################################
# Utility methods

def _copy_inputs(source_node, target_node):
    """Copy all the input connections from this node to the target node.

    :param hou.Node source_node: Soure node with inputs to copy.
    :param hou.Node target_node: Target node to receive the copied inputs.

    """

    input_connections = source_node.inputConnections()
    num_target_inputs = len(target_node.inputConnectors())

    if len(input_connections) > num_target_inputs:
        raise hou.InvalidInput(
            "Not enough inputs on target node. Cannot copy inputs from "
            "'%s' to '%s'" % (source_node, target_node)
        )
        
    for connection in input_connections:
        target_node.setInput(connection.inputIndex(),
            connection.inputNode())


def _copy_parm_values(source_node, target_node, excludes=None):
    """Copy matching parameter values from source node to target node.

    :param hou.Node source_node: Soure node with parm values to copy.
    :param hou.Node target_node: Target node to receive the copied parm values.
    :parm list excludes: List of parm names to exclude during copy.

    """

    if not excludes:
        excludes = []

    # build a parameter list from the source node, ignoring the excludes
    source_parms = [
        parm for parm in source_node.parms() if parm.name() not in excludes]

    for source_parm in source_parms:

        source_parm_template = source_parm.parmTemplate()

        # skip folder parms
        if isinstance(source_parm_template, hou.FolderSetParmTemplate):
            continue

        target_parm = target_node.parm(source_parm.name())

        # if the parm on the target node doesn't exist, skip it
        if target_parm is None:
            continue

        # if we have keys/expressions we need to copy them all.
        if source_parm.keyframes():
            for key in source_parm.keyframes():
                target_parm.setKeyframe(key)
        else:
            # if the parameter is a string, copy the raw string.
            if isinstance(source_parm_template, hou.StringParmTemplate):
                target_parm.set(source_parm.unexpandedString())
            # copy the evaluated value
            else:
                try:
                    target_parm.set(source_parm.eval())
                except TypeError:
                    # The pre- and post-script type comboboxes changed sometime around
                    # 16.5.439 to being string type parms that take the name of the language
                    # (hscript or python) instead of an integer index of the combobox item
                    # that's selected. To support both, we try the old way (which is how our
                    # otl is setup to work), and if that fails we then fall back on mapping
                    # the integer index from our otl's parm over to the string language name
                    # that the arnold node is expecting.
                    if source_parm.name().startswith("lpre") or source_parm.name().startswith("lpost"):
                        value_map = ["hscript", "python"]
                        target_parm.set(value_map[source_parm.eval()])
                    else:
                        raise

def _get_extra_plane_numbers(node):
    """Return a list of aov plane nubmers.
    
    :param hou.Node node: The node being acted upon.
    
    """

    return range(1, node.parm(TkArnoldNodeHandler.TK_EXTRA_PLANE_COUNT_PARM).eval() + 1)


def _move_outputs(source_node, target_node):
    """Moves all the output connections from source node to target node

    :param hou.Node source_node: Soure node with outputs to move.
    :param hou.Node target_node: Target node to receive the moved outputs.

    """

    for connection in source_node.outputConnections():
        output_node = connection.outputNode()
        output_node.setInput(connection.inputIndex(), target_node)


