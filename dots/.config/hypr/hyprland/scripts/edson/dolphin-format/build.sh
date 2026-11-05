#!/usr/bin/env bash
set -eu
src=$(cd "$(dirname "$0")" && pwd)
build=$(mktemp -d)
trap 'rm -r -- "$build"' EXIT
sdk=${II_FORMAT_SDK:-}
inc="$sdk$(qtpaths6 --query QT_INSTALL_HEADERS)"
moc="$sdk$(qtpaths6 --query QT_INSTALL_LIBEXECS)/moc"
kf="$sdk/usr/include/KF6"
dest="$HOME/.local/lib/ii-dolphin-plugins/generic"
"$moc" -I"$inc" -I"$inc"/{QtCore,QtGui,QtWidgets} "$src/places.cpp" -o "$build/places.moc"
"${CXX:-c++}" -std=c++17 -fPIC -shared -O2 -I"$build" -I"$inc" -I"$inc"/{QtCore,QtGui,QtWidgets,QtXml} \
  -I"$kf" -I"$kf"/{Solid,KIO,KIOFileWidgets,KBookmarks} "$src/places.cpp" -o "$build/libii-places-format.so" \
  -l:libKF6KIOFileWidgets.so.6 -l:libKF6Solid.so.6 -l:libQt6Widgets.so.6 -l:libQt6Gui.so.6 -l:libQt6Core.so.6
install -d "$dest"
install -m755 "$build/libii-places-format.so" "$dest/.ii-places-format.new"
mv -f "$dest/.ii-places-format.new" "$dest/libii-places-format.so"
