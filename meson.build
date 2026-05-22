project('adbgui', version: '0.3.0', meson_version: '>= 1.0.0')

python = import('python').find_installation('python3')
py_site = get_option('prefix') / 'lib' / 'python' + python.language_version() / 'site-packages'

install_subdir('src',
    install_dir: py_site,
    strip_directory: true
)

install_data('io.github.Alastt28.AdbGUI.metainfo.xml',
    install_dir: get_option('datadir') / 'metainfo'
)

install_data('data/icons/io.github.Alastt28.AdbGUI.svg',
    install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps'
)

install_data('io.github.Alastt28.AdbGUI.desktop',
    install_dir: get_option('datadir') / 'applications'
)

install_data('data/bin/bridge.apk',
    install_dir: get_option('datadir') / 'adbgui'
)

install_data('src/__main__.py',
    rename: 'adbgui',
    install_mode: 'rwxr-xr-x',
    install_dir: get_option('bindir')
)