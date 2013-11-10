# -*- coding: utf-8 -*-
#
# This file is part of NINJA-IDE (http://ninja-ide.org).
#
# NINJA-IDE is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# any later version.
#
# NINJA-IDE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with NINJA-IDE; If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import unicode_literals

import os

from ninja_ide.tools.logger import NinjaLogger
logger = NinjaLogger('ninja_ide.gui.explorer.tree_projects_widget')
DEBUG = logger.debug

from PyQt4.QtGui import QTreeView
from PyQt4.QtGui import QWidget
from PyQt4.QtGui import QScrollArea
from PyQt4.QtGui import QVBoxLayout
from PyQt4.QtGui import QAbstractItemView
from PyQt4.QtGui import QHeaderView
from PyQt4.QtGui import QFileDialog
from PyQt4.QtGui import QInputDialog
from PyQt4.QtGui import QMessageBox
from PyQt4.QtGui import QColor
from PyQt4.QtGui import QBrush
from PyQt4.QtGui import QLinearGradient
from PyQt4.QtGui import QMenu
from PyQt4.QtGui import QIcon
from PyQt4.QtGui import QStyle
from PyQt4.QtGui import QCursor
#from PyQt4.QtGui import QSizePolicy
from PyQt4.QtGui import QFontMetrics
from PyQt4.QtCore import Qt
from PyQt4.QtCore import SIGNAL
from PyQt4.QtCore import QUrl
from PyQt4.QtGui import QDesktopServices

from ninja_ide import translations
from ninja_ide.core import settings
from ninja_ide.core.file_handling import file_manager
from ninja_ide.tools import ui_tools
from ninja_ide.gui.ide import IDE
from ninja_ide.gui.dialogs import add_to_project
from ninja_ide.gui.dialogs import project_properties_widget
from ninja_ide.gui.explorer.explorer_container import ExplorerContainer
from ninja_ide.gui.explorer import actions
from ninja_ide.gui.explorer.nproject import NProject


def scrollable_wrapper(widget):
    scrollable = QScrollArea()
    scrollable.setWidget(widget)
    scrollable.setWidgetResizable(True)
    scrollable.setEnabled(True)
    return scrollable


class TreeHeader(QHeaderView):
    """
    SIGNALS:
    @headerClicked(QPoint)
    """

    def __init__(self):
        super(TreeHeader, self).__init__(Qt.Horizontal)
        self.title = ""
        self._is_current_project = False
        self._mouse_over = False
        self.setToolTip(translations.TR_PROJECT_OPTIONS)

    def _get_is_current_project(self):
        return self._is_current_project

    def _set_is_current_project(self, val):
        self._is_current_project = val
        self.repaint()

    is_current_project = property(_get_is_current_project,
                                  _set_is_current_project)

    def paintSection(self, painter, rect, logicalIndex):
        gradient = QLinearGradient(0, 0, 0, rect.height())
        if self._mouse_over:
            gradient.setColorAt(0.0, QColor("#808080"))
            gradient.setColorAt(1.0, QColor("#474747"))
        else:
            gradient.setColorAt(0.0, QColor("#727272"))
            gradient.setColorAt(1.0, QColor("#363636"))
        painter.fillRect(rect, QBrush(gradient))

        if self._is_current_project:
            painter.setPen(QColor(0, 204, 82))
        else:
            painter.setPen(QColor(Qt.white))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        font_metrics = QFontMetrics(painter.font())
        ypos = (rect.height() / 2) + (font_metrics.height() / 3)
        painter.drawText(10, ypos, self.title)

    def enterEvent(self, event):
        super(TreeHeader, self).enterEvent(event)
        self._mouse_over = True

    def leaveEvent(self, event):
        super(TreeHeader, self).leaveEvent(event)
        self._mouse_over = False

    def mousePressEvent(self, event):
        super(TreeHeader, self).mousePressEvent(event)
        self.emit(SIGNAL("headerClicked(QPoint)"), QCursor.pos())


class ProjectTreeColumn(QScrollArea):

    def __init__(self, *args, **kwargs):
        super(ProjectTreeColumn, self).__init__(*args, **kwargs)
        self._widget = QWidget()
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        self._widget.setLayout(vbox)
        self.setWidget(self._widget)
        self.setWidgetResizable(True)
        self.setEnabled(True)
        self.projects = []
        self._active_project = None

        connections = (
            {'target': 'main_container',
            'signal_name': 'addToProject(QString)',
            'slot': self._add_file_to_project},
        )
        IDE.register_service('tree_projects', self)
        IDE.register_signals('tree_projects', connections)
        ExplorerContainer.register_tab(translations.TR_TAB_PROJECTS, self)

    def install_tab(self):
        ide = IDE.get_service('ide')
        ui_tools.install_shortcuts(self, actions.PROJECTS_TREE_ACTIONS, ide)

    def open_project_folder(self):
        if settings.WORKSPACE:
            directory = settings.WORKSPACE
        else:
            directory = os.path.expanduser("~")

        folderName = QFileDialog.getExistingDirectory(self,
                self.tr("Open Project Directory"), directory)
        logger.debug("Choosing Foldername")
        if folderName:
            logger.debug("Opening %s" % folderName)
            ninjaide = IDE.get_service("ide")
            project = NProject(folderName)
            qfsm = ninjaide.filesystem.open_project(project)
            if qfsm:
                self.add_project(project)

    def _add_file_to_project(self, path):
        """Add the file for 'path' in the project the user choose here."""
        if self._active_project:
            pathProject = [self._active_project.project]
            addToProject = add_to_project.AddToProject(pathProject, self)
            addToProject.exec_()
            if not addToProject.pathSelected:
                return
            main_container = IDE.get_service('main_container')
            if not main_container:
                return
            editorWidget = main_container.get_current_editor()
            if not editorWidget.file_path:
                name = QInputDialog.getText(None,
                    self.tr("Add File To Project"), self.tr("File Name:"))[0]
                if not name:
                    QMessageBox.information(self, self.tr("Invalid Name"),
                        self.tr("The file name is empty, please enter a name"))
                    return
            else:
                name = file_manager.get_basename(editorWidget.file_path)
            path = file_manager.create_path(addToProject.pathSelected, name)
            try:
                path = file_manager.store_file_content(
                    path, editorWidget.get_text(), newFile=True)
                if path != editorWidget.ID:
                    main_container.remove_standalone_watcher(
                        editorWidget.ID)
                editorWidget.ID = path
                self.add_existing_file(path)
                self.emit(SIGNAL("changeWindowTitle(QString)"), path)
                name = file_manager.get_basename(path)
                main_container.actualTab.setTabText(
                    main_container.actualTab.currentIndex(), name)
                editorWidget._file_saved()
            except file_manager.NinjaFileExistsException as ex:
                QMessageBox.information(self, self.tr("File Already Exists"),
                    (self.tr("Invalid Path: the file '%s' already exists.") %
                        ex.filename))
        else:
            pass
            # Message about no project

    def add_project(self, project):
        if project not in self.projects:
            ptree = TreeProjectsWidget(project)
            self.connect(ptree, SIGNAL("setActiveProject(PyQt_PyObject)"),
                self._set_active_project)
            self.connect(ptree, SIGNAL("closeProject(PyQt_PyObject)"),
                self._close_project)
            pmodel = project.model
            ptree.setModel(pmodel)
            ptree.header().title = project.name
            pindex = pmodel.index(pmodel.rootPath())
            ptree.setRootIndex(pindex)
            #self._widget.layout().addWidget(scrollable_wrapper(ptree))
            self._widget.layout().addWidget(ptree)
            if self._active_project is None:
                ptree.set_default_project()
            self.projects.append(ptree)

    def _close_project(self, widget):
        """Close the project related to the tree widget."""
        self.projects.remove(widget)
        if self._active_project == widget and len(self.projects) > 0:
            self.projects[0].set_default_project()
        self._widget.layout().removeWidget(widget)
        widget.deleteLater()

    def _set_active_project(self, tree_proj):
        if self._active_project is not None:
            self._active_project.set_default_project(False)
        self._active_project = tree_proj


class TreeProjectsWidget(QTreeView):

###############################################################################
# TreeProjectsWidget SIGNALS
###############################################################################

    """
    runProject()
    setActiveProject(PyQt_PyObject)
    closeProject(QString)
    closeFilesFromProjectClosed(QString)
    addProjectToConsole(QString)
    removeProjectFromConsole(QString)
    projectPropertiesUpdated(QTreeWidgetItem)
    """

###############################################################################

    #Extra context menu 'all' indicate a menu for ALL LANGUAGES!
    extra_menus = {'all': []}
    #Extra context menu by scope all is for ALL the TREE ITEMS!
    extra_menus_by_scope = {'project': [], 'folder': [], 'file': []}

    images = {
        'py': ":img/tree-python",
        'jpg': ":img/tree-image",
        'png': ":img/tree-image",
        'html': ":img/tree-html",
        'css': ":img/tree-css",
        'ui': ":img/designer"}

    def __format_tree(self):
        """If not called after setting model, all the column format
        options are reset to default when the model is set"""
        self.setSelectionMode(QTreeView.SingleSelection)
        self.setAnimated(True)

        t_header = TreeHeader()
        self.connect(t_header, SIGNAL("headerClicked(QPoint)"),
            lambda point: self._menu_context_tree(point, True))
        self.setHeader(t_header)
        t_header.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        t_header.setResizeMode(0, QHeaderView.Stretch)
        t_header.setStretchLastSection(False)
        t_header.setClickable(True)

        self.hideColumn(1)  # Size
        self.hideColumn(2)  # Type
        self.hideColumn(3)  # Modification date

        #TODO: We need to expand the widget to be as big as the real area
        #that contains all the visible tree items, the code below
        #tries to detect when that area grows to adjust the size of the
        #widget, but i'm not sure this is the proper approach
        #self.connect(self.verticalScrollBar(),
            #SIGNAL("rangeChanged(int, int)"), self.test)

    #def test(self, minimum, maximum):
        #print self.height(), self.viewport().size().height()
        ##self.setFixedHeight()

    def setModel(self, model):
        super(TreeProjectsWidget, self).setModel(model)
        self.__format_tree()
        #Activated is said to do the right thing on every system
        self.connect(self, SIGNAL("activated(const QModelIndex &)"),
                    self._open_file)

    def __init__(self, project, state_index=list()):
        super(TreeProjectsWidget, self).__init__()
        self.project = project
        self._added_to_console = False
        #self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.__format_tree()

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.connect(self, SIGNAL(
            "customContextMenuRequested(const QPoint &)"),
            self._menu_context_tree)

        self.connect(project, SIGNAL("projectNameUpdated(QString)"),
            self._update_header_title)
        self.expanded.connect(self._item_expanded)
        self.collapsed.connect(self._item_collapsed)
        self.state_index = list()
        self._folding_menu = FoldingContextMenu(self)

    def _update_header_title(self, title):
        self.header().title = title

    def _item_collapsed(self, tree_item):
        """Store status of item when collapsed"""
        path = self.model().filePath(tree_item)
        if path in self.state_index:
            path_index = self.state_index.index(path)
            self.state_index.pop(path_index)

    def _item_expanded(self, tree_item):
        """Store status of item when expanded"""
        path = self.model().filePath(tree_item)
        if path not in self.state_index:
            self.state_index.append(path)

    def add_extra_menu(self, menu, lang='all'):
        '''
        Add an extra menu for the given language
        @lang: string with the form 'py', 'php', 'json', etc
        '''
        #remove blanks and replace dots Example(.py => py)
        lang = lang.strip().replace('.', '')
        self.extra_menus.setdefault(lang, [])
        self.extra_menus[lang].append(menu)

    def add_extra_menu_by_scope(self, menu, scope):
        '''
        Add an extra menu for the given language
        @scope: string with the menu scope (all, project, folder, item)
        '''
        if scope.project:
            self.extra_menus_by_scope['project'].append(menu)
        if scope.folder:
            self.extra_menus_by_scope['folder'].append(menu)
        if scope.file:
            self.extra_menus_by_scope['file'].append(menu)

    def _menu_context_tree(self, point, isRoot=False):
        index = self.indexAt(point)
        if not index.isValid() and not isRoot:
            return

        handler = None
        menu = QMenu(self)
        if isRoot or self.model().isDir(index):
            self._add_context_menu_for_folders(menu, isRoot)
        else:
            filename = self.model().fileName(index)
            lang = file_manager.get_file_extension(filename)
            self._add_context_menu_for_files(menu, lang)
        if isRoot:
            #get the extra context menu for this projectType
            handler = settings.get_project_type_handler(
                self.project.project_type)
            self._add_context_menu_for_root(menu)

        menu.addMenu(self._folding_menu)

        #menu for all items (legacy API)!
        extra_menus = self.extra_menus.get('all', ())
        #menu for all items!
        for m in extra_menus:
            if isinstance(m, QMenu):
                menu.addSeparator()
                menu.addMenu(m)
        #menu for the Project Type(if present)
        if handler:
            for m in handler.get_context_menus():
                if isinstance(m, QMenu):
                    menu.addSeparator()
                    menu.addMenu(m)
        #show the menu!
        menu.exec_(QCursor.pos())

    def _add_context_menu_for_root(self, menu):
        menu.addSeparator()
        actionRunProject = menu.addAction(QIcon(
            ":img/play"), self.tr("Run Project"))
        self.connect(actionRunProject, SIGNAL("triggered()"),
            SIGNAL("runProject()"))
        actionMainProject = menu.addAction(self.tr("Set as Main Project"))
        self.connect(actionMainProject, SIGNAL("triggered()"),
            self.set_default_project)
        if self._added_to_console:
            actionRemoveFromConsole = menu.addAction(
                self.tr("Remove this Project from the Python Console"))
            self.connect(actionRemoveFromConsole, SIGNAL("triggered()"),
                self._remove_project_from_console)
        else:
            actionAdd2Console = menu.addAction(
                self.tr("Add this Project to the Python Console"))
            self.connect(actionAdd2Console, SIGNAL("triggered()"),
                self._add_project_to_console)
        actionProperties = menu.addAction(QIcon(":img/pref"),
            self.tr("Project Properties"))
        self.connect(actionProperties, SIGNAL("triggered()"),
            self.open_project_properties)

        menu.addSeparator()
        action_close = menu.addAction(
            self.style().standardIcon(QStyle.SP_DialogCloseButton),
            self.tr("Close Project"))
        self.connect(action_close, SIGNAL("triggered()"),
            self._close_project)
        #menu for the project
        for m in self.extra_menus_by_scope['project']:
            if isinstance(m, QMenu):
                menu.addSeparator()
                menu.addMenu(m)

    def _add_context_menu_for_folders(self, menu, isRoot):
        action_add_file = menu.addAction(QIcon(":img/new"),
                    self.tr("Add New File"))
        self.connect(action_add_file, SIGNAL("triggered()"),
            self._add_new_file)
        action_add_folder = menu.addAction(QIcon(
            ":img/openProj"), self.tr("Add New Folder"))
        self.connect(action_add_folder, SIGNAL("triggered()"),
            self._add_new_folder)
        action_create_init = menu.addAction(
            self.tr("Create '__init__' Complete"))
        self.connect(action_create_init, SIGNAL("triggered()"),
            self._create_init)
        if not isRoot:
            #Folders but not the root
            action_remove_folder = menu.addAction(self.tr("Remove Folder"))
            self.connect(action_remove_folder, SIGNAL("triggered()"),
                self._delete_folder)
            for m in self.extra_menus_by_scope['folder']:
                if isinstance(m, QMenu):
                    menu.addSeparator()
                    menu.addMenu(m)

    def _add_context_menu_for_files(self, menu, lang):
        action_rename_file = menu.addAction(self.tr("Rename File"))
        action_move_file = menu.addAction(self.tr("Move File"))
        action_copy_file = menu.addAction(self.tr("Copy File"))
        action_remove_file = menu.addAction(
            self.style().standardIcon(QStyle.SP_DialogCloseButton),
            self.tr("Delete File"))
        self.connect(action_remove_file, SIGNAL("triggered()"),
            self._delete_file)
        self.connect(action_rename_file, SIGNAL("triggered()"),
            self._rename_file)
        self.connect(action_copy_file, SIGNAL("triggered()"),
            self._copy_file)
        self.connect(action_move_file, SIGNAL("triggered()"),
            self._move_file)
        #Allow to edit Qt UI files with the appropiate program
        if lang == 'ui':
            action_edit_ui_file = menu.addAction(self.tr("Edit UI File"))
            self.connect(action_edit_ui_file, SIGNAL("triggered()"),
                self._edit_ui_file)
        #menu per file language (legacy plugin API)!
        for m in self.extra_menus.get(lang, ()):
            if isinstance(m, QMenu):
                menu.addSeparator()
                menu.addMenu(m)
        #menu for files
        for m in self.extra_menus_by_scope['file']:
            if isinstance(m, QMenu):
                menu.addSeparator()
                menu.addMenu(m)

    def _add_project_to_console(self):
        tools_dock = IDE.get_service('tools_dock')
        if tools_dock:
            tools_dock.add_project_to_console(self.project.path)
            self._added_to_console = True

    def _remove_project_from_console(self):
        tools_dock = IDE.get_service('tools_dock')
        if tools_dock:
            tools_dock.remove_project_from_console(self.project.path)
            self._added_to_console = False

    def _open_file(self, model_index):
        path = self.model().filePath(model_index)
        main_container = IDE.get_service('main_container')
        logger.debug("tried to get main container")
        if main_container:
            logger.debug("will call open file")
            main_container.open_file(path)

    def set_default_project(self, value=True):
        self.header().is_current_project = value
        if value:
            self.emit(SIGNAL("setActiveProject(PyQt_PyObject)"), self)

    def open_project_properties(self):
        proj = project_properties_widget.ProjectProperties(self.project, self)
        proj.show()

    def _close_project(self):
        self.emit(SIGNAL("closeProject(PyQt_PyObject)"), self)

    def _create_init(self):
        path = self.model().filePath(self.currentIndex())
        try:
            file_manager.create_init_file_complete(path)
        except file_manager.NinjaFileExistsException as ex:
            QMessageBox.information(self, self.tr("Create INIT fail"),
                ex.message)

    def _add_new_file(self):
        path = self.model().filePath(self.currentIndex())
        result = QInputDialog.getText(self, self.tr("New File"),
            self.tr("Enter the File Name:"))
        fileName = result[0]

        if result[1] and fileName.strip() != '':
            try:
                fileName = os.path.join(path, fileName)
                fileName = file_manager.store_file_content(
                    fileName, '', newFile=True)
                main_container = IDE.get_service('main_container')
                if main_container:
                    main_container.open_file(fileName)
            except file_manager.NinjaFileExistsException as ex:
                QMessageBox.information(self, self.tr("File Already Exists"),
                    (self.tr("Invalid Path: the file '%s' already exists.") %
                        ex.filename))

    #FIXME
    def add_existing_file(self, path):
        relative = file_manager.convert_to_relative(
            self._actualProject.path, path)
        paths = relative.split(os.sep)[:-1]
        itemParent = self._actualProject
        for p in paths:
            for i in range(itemParent.childCount()):
                item = itemParent.child(i)
                if item.text(0) == p:
                    itemParent = item
                    break
        itemParent.setSelected(True)
        name = file_manager.get_basename(path)
        subitem = ProjectItem(itemParent, name, file_manager.get_folder(path))
        subitem.setToolTip(0, name)
        subitem.setIcon(0, self._get_file_icon(name))
        itemParent.setExpanded(True)

    def _add_new_folder(self):
        path = self.model().filePath(self.currentIndex())
        result = QInputDialog.getText(self, self.tr("New Folder"),
            self.tr("Enter the Folder Name:"))
        folderName = result[0]

        if result[1] and folderName.strip() != '':
            folderName = os.path.join(path, folderName)
            file_manager.create_folder(folderName)

    def _delete_file(self):
        path = self.model().filePath(self.currentIndex())
        val = QMessageBox.question(self, self.tr("Delete File"),
                self.tr("Do you want to delete the following file: ")
                + path,
                QMessageBox.Yes, QMessageBox.No)
        if val == QMessageBox.Yes:
            path = file_manager.create_path(path)
            file_manager.delete_file(path)
            main_container = IDE.get_service('main_container')
            if main_container and main_container.is_open(path):
                main_container.close_deleted_file(path)

    def _delete_folder(self):
        path = self.model().filePath(self.currentIndex())
        val = QMessageBox.question(self, self.tr("Delete Folder"),
                self.tr("Do you want to delete the following folder: ")
                + path,
                QMessageBox.Yes, QMessageBox.No)
        if val == QMessageBox.Yes:
            file_manager.delete_folder(path)

    def _rename_file(self):
        path = self.model().filePath(self.currentIndex())
        name = file_manager.get_basename(path)
        result = QInputDialog.getText(self, self.tr("Rename File"),
            self.tr("Enter New File Name:"), text=name)
        fileName = result[0]

        if result[1] and fileName.strip() != '':
            fileName = os.path.join(
                file_manager.get_folder(path), fileName)
            if path == fileName:
                return
            try:
                fileName = file_manager.rename_file(path, fileName)
                name = file_manager.get_basename(fileName)
                main_container = IDE.get_service('main_container')
                if main_container and main_container.is_open(path):
                    main_container.change_open_tab_name(path, fileName)
            except file_manager.NinjaFileExistsException as ex:
                QMessageBox.information(self, self.tr("File Already Exists"),
                    (self.tr("Invalid Path: the file '%s' already exists.") %
                        ex.filename))

    def _copy_file(self):
        #get the selected QTreeWidgetItem
        path = self.model().filePath(self.currentIndex())
        name = file_manager.get_basename(path)
        pathProjects = [p.path for p in self.get_open_projects()]
        addToProject = add_to_project.AddToProject(pathProjects, self)
        addToProject.setWindowTitle(self.tr("Copy File to"))
        addToProject.exec_()
        if not addToProject.pathSelected:
            return
        name = QInputDialog.getText(self, self.tr("Copy File"),
            self.tr("File Name:"), text=name)[0]
        if not name:
            QMessageBox.information(self, self.tr("Invalid Name"),
                self.tr("The file name is empty, please enter a name"))
            return
        path = file_manager.create_path(addToProject.pathSelected, name)
        try:
            content = file_manager.read_file_content(path)
            path = file_manager.store_file_content(path, content, newFile=True)
            self.add_existing_file(path)
        except file_manager.NinjaFileExistsException as ex:
                QMessageBox.information(self, self.tr("File Already Exists"),
                    (self.tr("Invalid Path: the file '%s' already exists.") %
                        ex.filename))

    def _move_file(self):
        path = self.model().filePath(self.currentIndex())
        pathProjects = [p.path for p in self.get_open_projects()]
        addToProject = add_to_project.AddToProject(pathProjects, self)
        addToProject.setWindowTitle(self.tr("Copy File to"))
        addToProject.exec_()
        if not addToProject.pathSelected:
            return
        name = file_manager.get_basename(path)
        path = file_manager.create_path(addToProject.pathSelected, name)
        try:
            content = file_manager.read_file_content(path)
            path = file_manager.store_file_content(path, content, newFile=True)
            file_manager.delete_file(path)
            self.add_existing_file(path)
            # Update path of opened file
            main = IDE.get_service('main_container')
            if main and main.is_open(path):
                widget = main.get_widget_for_path(path)
                if widget:
                    widget.ID = path
        except file_manager.NinjaFileExistsException as ex:
                QMessageBox.information(self, self.tr("File Already Exists"),
                    (self.tr("Invalid Path: the file '%s' already exists.") %
                        ex.filename))

    def _edit_ui_file(self):
        path = self.model().filePath(self.currentIndex())
        pathForFile = "file://%s" % path
        #open the correct program to edit Qt UI files!
        QDesktopServices.openUrl(QUrl(pathForFile, QUrl.TolerantMode))

    def _get_file_icon(self, fileName):
        return QIcon(self.images.get(file_manager.get_file_extension(fileName),
            ":img/tree-generic"))

    def get_item_for_path(self, path):
        #FIXME use model index search by path in model
        items = self.findItems(file_manager.get_basename(path),
            Qt.MatchRecursive, 0)
        folder = file_manager.get_folder(path)
        for item in items:
            if file_manager.belongs_to_folder(folder, item.path):
                return item

    def get_project_by_name(self, projectName):
        """Return the name of the project item based on the project name."""
        # Return the item or None if it's not found
        for item in list(self._projects.values()):
            if item.name == projectName:
                return item

    def get_selected_project_path(self):
        if self._actualProject:
            return self._actualProject.path
        return None

    def get_selected_project_type(self):
        rootItem = self._get_project_root()
        return rootItem.projectType

    def get_selected_project_lang(self):
        rootItem = self._get_project_root()
        return rootItem.lang()

    def get_open_projects(self):
        return list(self._projects.values())

    def is_open(self, path):
        return len([True for item in list(self._projects.values())
            if item.path == path]) != 0

    def _set_current_project(self, path):
        for item in list(self._projects.values()):
            if item.path == path:
                self.set_default_project(item)
                break

    def _close_open_projects(self):
        self.__enableCloseNotification = False
        for i in range(self.topLevelItemCount()):
            self.setCurrentItem(self.topLevelItem(0))
            self._close_project()
        self.__enableCloseNotification = True
        self._projects = {}


class FoldingContextMenu(QMenu):
    """
    This class represents a menu for Folding/Unfolding task
    """

    def __init__(self, tree):
        super(FoldingContextMenu, self).__init__()
        self.setTitle(self.tr("Fold/Unfold"))
        self._tree = tree
        fold_project = self.addAction(self.tr("Fold the project"))
        unfold_project = self.addAction(self.tr("Unfold the project"))
        self.addSeparator()
        fold_all_projects = self.addAction(self.tr("Fold all projects"))
        unfold_all_projects = self.addAction(self.tr("Unfold all projects"))

        self.connect(fold_project, SIGNAL("triggered()"),
            lambda: self._fold_unfold_project(False))
        self.connect(unfold_project, SIGNAL("triggered()"),
            lambda: self._fold_unfold_project(True))
        self.connect(fold_all_projects, SIGNAL("triggered()"),
            self._fold_all_projects)
        self.connect(unfold_all_projects, SIGNAL("triggered()"),
            self._unfold_all_projects)

    def _recursive_fold_unfold(self, item, expand):
        if item.isFolder:
            item.setExpanded(expand)
        for index in range(item.childCount()):
            child = item.child(index)
            self._recursive_fold_unfold(child, expand)

    def _fold_unfold_project(self, expand):
        """
        Fold the current project
        """
        root = self._tree._get_project_root(item=self._tree.currentItem())
        childs = root.childCount()
        if childs:
            root.setExpanded(expand)

        for index in range(childs):
            item = root.child(index)
            self._recursive_fold_unfold(item, expand)

    def _fold_all_projects(self):
        """
        Fold all projects
        """
        self._tree.collapseAll()

    def _unfold_all_projects(self):
        """
        Unfold all project
        """
        self._tree.expandAll()


if settings.SHOW_PROJECT_EXPLORER:
    projectsColumn = ProjectTreeColumn()
else:
    projectsColumn = None