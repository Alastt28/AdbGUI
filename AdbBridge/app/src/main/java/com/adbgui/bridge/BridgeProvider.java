package com.adbgui.bridge;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.content.pm.PackageManager;
import android.content.pm.ApplicationInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileNotFoundException;
import java.util.List;

public class BridgeProvider extends ContentProvider {
    @Override
    public boolean onCreate() { return true; }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        MatrixCursor cursor = new MatrixCursor(new String[]{"status", "path"});
        PackageManager pm = getContext().getPackageManager();
        String path = uri.getPath();

        if (path == null) return cursor;

        if (path.equals("/all")) {
            MatrixCursor appsCursor = new MatrixCursor(new String[]{"package", "label"});
            List<ApplicationInfo> apps = pm.getInstalledApplications(PackageManager.GET_META_DATA);
            for (ApplicationInfo ai : apps) {
                appsCursor.addRow(new Object[]{ai.packageName, ai.loadLabel(pm).toString()});
            }
            return appsCursor;
        }

        else if (path.equals("/export_icons")) {
            File cacheDir = new File(getContext().getExternalCacheDir(), "icons");
            if (!cacheDir.exists()) cacheDir.mkdirs();

            List<ApplicationInfo> apps = pm.getInstalledApplications(0);
            for (ApplicationInfo ai : apps) {
                try {
                    File iconFile = new File(cacheDir, ai.packageName + ".png");
                    if (iconFile.exists()) continue;

                    Drawable icon = ai.loadIcon(pm);

                    int w = icon.getIntrinsicWidth() > 0 ? icon.getIntrinsicWidth() : 192;
                    int h = icon.getIntrinsicHeight() > 0 ? icon.getIntrinsicHeight() : 192;

                    Bitmap bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
                    Canvas canvas = new Canvas(bitmap);
                    icon.setBounds(0, 0, canvas.getWidth(), canvas.getHeight());
                    icon.draw(canvas);

                    FileOutputStream out = new FileOutputStream(iconFile);
                    bitmap.compress(Bitmap.CompressFormat.PNG, 80, out);
                    out.close();
                } catch (Exception e) { /* пропуск битых иконок */ }
            }
            cursor.addRow(new Object[]{"done", cacheDir.getAbsolutePath()});
            return cursor;
        }

        return cursor;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (uri.getPath() != null && uri.getPath().startsWith("/icon/")) {
            String packageName = uri.getLastPathSegment();
            PackageManager pm = getContext().getPackageManager();

            try {
                Drawable icon = pm.getApplicationIcon(packageName);

                int w = icon.getIntrinsicWidth() > 0 ? icon.getIntrinsicWidth() : 192;
                int h = icon.getIntrinsicHeight() > 0 ? icon.getIntrinsicHeight() : 192;

                Bitmap bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
                Canvas canvas = new Canvas(bitmap);
                icon.setBounds(0, 0, canvas.getWidth(), canvas.getHeight());
                icon.draw(canvas);

                // Сохраняем во временный файл для передачи через ADB
                File cacheFile = new File(getContext().getCacheDir(), "icon_" + packageName + ".png");
                FileOutputStream out = new FileOutputStream(cacheFile);
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
                out.flush();
                out.close();

                return ParcelFileDescriptor.open(cacheFile, ParcelFileDescriptor.MODE_READ_ONLY);
            } catch (Exception e) {
                throw new FileNotFoundException("No result found");
            }
        }
        return super.openFile(uri, mode);
    }

    @Override public String getType(Uri uri) { return "image/png"; }
    @Override public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) { return 0; }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) { return 0; }
}
