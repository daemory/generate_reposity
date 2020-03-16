#!/usr/bin/env python

import itertools
import xml.dom.minidom
import os
import sys

def is_python3():
  return sys.version_info[0] == 3

if is_python3():
  import urllib.parse
  print("python3")
else:
  import imp
  import urlparse
  urllib = imp.new_module('urllib')
  urllib.parse = urlparse
  print("python2")

MANIFEST_FILE_NAME = 'manifest.xml'
REPOSITY_OUTPUT = 'output'
BRANCH_NAME = 'master'

class ManifestParseError(Exception):
  """Failed to parse the manifest file.
  """

class XmlManifest(object):
  """manages the repo configuration file"""

  def __init__(self, repodir):
      self.repodir = os.path.abspath(repodir)
      self.topdir = os.path.dirname(self.repodir)
      self.manifestFile = os.path.join(self.repodir, MANIFEST_FILE_NAME)
      self.project_objects = os.path.join(self.repodir, "project-objects")
      self.projects = os.path.join(self.repodir, "projects")
      self.worktree = os.path.join(self.repodir, "manifests")
      self.output = os.path.join(self.repodir, REPOSITY_OUTPUT)

  def _ParseManifestXml(self, path, include_root):
    try:
      root = xml.dom.minidom.parse(path)
    except (OSError, xml.parsers.expat.ExpatError) as e:
      raise ManifestParseError("error parsing manifest %s: %s" % (path, e))

    if not root or not root.childNodes:
      raise ManifestParseError("no root node in %s" % (path,))

    for manifest in root.childNodes:
      if manifest.nodeName == 'manifest':
        break
    else:
      raise ManifestParseError("no <manifest> in %s" % (path,))

    nodes = []
    for node in manifest.childNodes:
      if node.nodeName == 'include':
        name = self._reqatt(node, 'name')
        fp = os.path.join(include_root, name)
        if not os.path.isfile(fp):
          raise ManifestParseError("include %s doesn't exist or isn't a file"
              % (name,))
        try:
          nodes.extend(self._ParseManifestXml(fp, include_root))
        # should isolate this to the exact exception, but that's
        # tricky.  actual parsing implementation may vary.
        except (KeyboardInterrupt, RuntimeError, SystemExit):
          raise
        except Exception as e:
          raise ManifestParseError(
              "failed parsing included manifest %s: %s" % (name, e))
      else:
        nodes.append(node)
    return nodes

  def _Load(self):
    nodes = []
    nodes.append(self._ParseManifestXml(self.manifestFile,
                                          self.worktree))
    try:
      self._ParseManifest(nodes)
    except ManifestParseError as e:
      # There was a problem parsing, unload ourselves in case they catch
      # this error and try again later, we will show the correct error
      print("_ParseManifest error")
      raise e

  def _ParseManifest(self, node_list):
    for node in itertools.chain(*node_list):
      if node.nodeName == 'manifest-server':
        url = self._reqatt(node, 'url')
        if self._manifest_server is not None:
          raise ManifestParseError(
              'duplicate manifest-server in %s' %
              (self.manifestFile))
        self._manifest_server = url

  def _reqatt(self, node, attname):
    """
    reads a required attribute from the node.
    """
    v = node.getAttribute(attname)
    if not v:
      raise ManifestParseError("no %s in <%s> within %s" %
            (attname, node.nodeName, self.manifestFile))
    return v

  def GenerateReposity(self):
    """
    generate reposity for gerrit server
    """
    nodes = []
    nodes.append(self._ParseManifestXml(self.manifestFile,
                                          self.worktree))
    for node in itertools.chain(*nodes):
        if node.nodeName == 'project':
            name = self._reqatt(node, 'name')
            path = node.getAttribute('path')
            if not path:
                path = name
            if path.startswith('/'):
                raise ManifestParseError("project %s path cannot be absolute in %s" %
                      (name, self.manifestFile))
            print("project name:" + name + " path:" + path)
            self._CloneBare(os.path.join(self.topdir, path), os.path.join(self.output, name))

  def _CloneBare(self, path_from, path_to):
      """
      make bare reposity
      """
      cur_dir = os.getcwd()
      path_to = path_to + ".git"
      cmd_clone = "git clone --bare " + path_from + " " + path_to
      if os.path.isdir(path_from):
          print(cmd_clone)
          os.system(cmd_clone)
      else:
          print(path_from + "not exsits")
          return
      os.chdir(path_to)

      cmd_create_branch = "git branch " + BRANCH_NAME
      print(cmd_create_branch)
      os.system(cmd_create_branch)
      cmd_rm_remote = "git remote rm origin"
      print(cmd_rm_remote)
      os.system(cmd_rm_remote)

      os.chdir(cur_dir)

if __name__ == '__main__':
    if not os.path.isfile(".repo/manifest.xml"):
        print('".repo/manifest.xml" not exists')
    else:
        xml_manifest = XmlManifest(os.path.join(os.getcwd(), ".repo"))
        xml_manifest.GenerateReposity()
