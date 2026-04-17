package com.adbgui.bridge;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.content.pm.PackageManager;
import android.content.pm.ApplicationInfo;
import java.util.List;

public class BridgeProvider extends ContentProvider {
    @Override
    public boolean onCreate() { return true; }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        MatrixCursor cursor = new MatrixCursor(new String[]{"package", "label"});
        PackageManager pm = getContext().getPackageManager();

        if (uri.getPath().equals("/all")) {
            List<ApplicationInfo> apps = pm.getInstalledApplications(PackageManager.GET_META_DATA | PackageManager.MATCH_DISABLED_COMPONENTS);
            for (ApplicationInfo ai : apps) {
                String label = ai.loadLabel(pm).toString();
                cursor.addRow(new Object[]{ai.packageName, label});
            }
        } else {
            String packageName = uri.getLastPathSegment();
            try {
                ApplicationInfo ai = pm.getApplicationInfo(packageName, PackageManager.GET_META_DATA);
                String label = ai.loadLabel(pm).toString();
                cursor.addRow(new Object[]{packageName, label});
            } catch (Exception e) {
                cursor.addRow(new Object[]{packageName, packageName});
            }
        }
        return cursor;
    }

    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) { return 0; }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) { return 0; }
}