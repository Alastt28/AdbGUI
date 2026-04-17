pkgdatadir = get_option('datadir') / meson.project_name()
gnome = import('gnome')
python = import('python')
py_installation = python.find_installation('python3')

libadwaita_dep = dependency('libadwaita-1', version: '>= 1.5')
blueprint_compiler = find_program('blueprint-compiler', required: true)

blueprints = [
  'window.blp',
  'app_row.blp'
]

compiled_ui = []
foreach blp_name : blueprints
  target_id = blp_name.underscorify()

  compiled_ui += custom_target(
    target_id,
    input: blp_name,
    output: blp_name.replace('.blp', '.ui'),
    command: [blueprint_compiler, 'compile', '--output', '@OUTPUT@', '@INPUT@']
  )
endforeach
app_resources = gnome.compile_resources('org.adb.gui',
  'org.adb.gui.gresource.xml',
  gresource_bundle: true,
  source_dir: meson.current_build_dir(),
  dependencies: compiled_ui,
  install: true,
  install_dir: pkgdatadir,
)

bin_conf = configuration_data()
bin_conf.set('PYTHON', py_installation.full_path())
bin_conf.set('PACKAGE_VERSION', meson.project_version())
bin_conf.set('PACKAGE_NAME', meson.project_name())
bin_conf.set('prefix', get_option('prefix'))
bin_conf.set('libdir', get_option('prefix') / get_option('libdir'))
bin_conf.set('datadir', get_option('prefix') / get_option('datadir'))
bin_conf.set('resource_path', '/org/adb/gui')

python_sources = [
  'main.py',
  'window.py',
]

install_data(python_sources, install_dir: pkgdatadir)

configure_file(
  input: 'org.adb.gui.in',
  output: 'org.adb.gui',
  configuration: bin_conf,
  install: true,
  install_dir: get_option('bindir')
)