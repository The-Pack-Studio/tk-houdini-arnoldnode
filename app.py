# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Arnold Output node App for use with Toolkit's Houdini engine.
"""

import sgtk


class TkArnoldNodeApp(sgtk.platform.Application):
    """The Arnold Output Node."""

    def init_app(self):
        """Initialize the app."""

        tk_houdini_arnold = self.import_module("tk_houdini_arnoldnode")
        self.handler = tk_houdini_arnold.TkArnoldNodeHandler(self)

    def convert_to_regular_arnold_nodes(self):
        """Convert Toolkit Arnold nodes to regular Arnold nodes.

        Convert all Tooklit Arnold nodes found in the current script to 
        regular Arnold nodes. Additional Toolkit information will be stored in
        user data named 'tk_*'

        Example usage::

        >>> import sgtk
        >>> eng = sgtk.platform.current_engine()
        >>> app = eng.apps["tk-houdini-arnoldnode"]
        >>> app.convert_to_regular_arnold_nodes()

        """

        self.log_debug(
            "Converting Toolkit Arnold nodes to built-in Arnold nodes.")
        tk_houdini_arnold = self.import_module("tk_houdini_arnoldnode")
        tk_houdini_arnold.TkArnoldNodeHandler.\
            convert_to_regular_arnold_nodes(self)

    def convert_back_to_tk_arnold_nodes(self):
        """Convert regular Arnold nodes back to Toolkit Arnold nodes.

        Convert any regular Arnold nodes that were previously converted
        from Toolkit Arnold nodes back into Toolkit Arnold nodes.

        Example usage::

        >>> import sgtk
        >>> eng = sgtk.platform.current_engine()
        >>> app = eng.apps["tk-houdini-arnoldnode"]
        >>> app.convert_back_to_tk_arnold_nodes()

        """

        self.log_debug(
            "Converting built-in Arnold nodes back to Toolkit Arnold nodes.")
        tk_houdini_arnold = self.import_module("tk_houdini_arnoldnode")
        tk_houdini_arnold.TkArnoldNodeHandler.\
            convert_back_to_tk_arnold_nodes(self)

    def get_nodes(self):
        """
        Returns a list of hou.node objects for each tk arnold node.

        Example usage::

        >>> import sgtk
        >>> eng = sgtk.platform.current_engine()
        >>> app = eng.apps["tk-houdini-arnoldnode"]
        >>> tk_arnold_nodes = app.get_nodes()
        """

        self.log_debug("Retrieving tk-houdini-arnold nodes...")
        tk_houdini_arnold = self.import_module("tk_houdini_arnoldnode")
        nodes = tk_houdini_arnold.TkarnoldNodeHandler.\
            get_all_tk_arnold_nodes()
        self.log_debug("Found %s tk-houdini-arnold nodes." % (len(nodes),))
        return nodes

    def get_output_path(self, node):
        """
        Returns the evaluated output path for the supplied node.

        Example usage::

        >>> import sgtk
        >>> eng = sgtk.platform.current_engine()
        >>> app = eng.apps["tk-houdini-arnoldnode"]
        >>> output_path = app.get_output_path(tk_arnold_node)
        """

        self.log_debug("Retrieving output path for %s" % (node,))
        tk_houdini_arnold = self.import_module("tk_houdini_arnoldnode")
        output_path = tk_houdini_arnold.TkArnoldNodeHandler.\
            get_output_path(node)
        self.log_debug("Retrieved output path: %s" % (output_path,))
        return output_path

    def get_work_file_template(self):
        """
        Returns the configured work file template for the app.
        """

        return self.get_template("work_file_template")