package org.mfilm.sony;

import java.io.File;
import java.io.IOException;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Pattern;

/** Match a single shutter to a new DCIM file while Sony's writer is running. */
final class CaptureFiles {
    private static final Pattern FOLDER=Pattern.compile("[1-9][0-9]{2}[A-Za-z0-9_]{5}");
    private static final Pattern RAW=Pattern.compile("[A-Za-z0-9_]{8}\\.[Aa][Rr][Ww]");
    private final Set<String> before;
    private String observed;
    private long previousSize=-1;
    private int unchanged;

    CaptureFiles(File dcim) throws IOException { before=list(dcim); }

    private static Set<String> list(File dcim) throws IOException {
        File[] folders=dcim.listFiles();
        if(folders==null)throw new IOException("Cannot read DCIM");
        Set<String> result=new HashSet<String>();
        for(File folder:folders){
            if(!FOLDER.matcher(folder.getName()).matches() || folder.isFile())continue;
            String[] names=folder.list();
            if(names==null)throw new IOException("Cannot read "+folder.getName());
            for(String name:names)if(RAW.matcher(name).matches())result.add(new File(folder,name).getPath());
        }
        return result;
    }

    String stableFile(File dcim) throws IOException {
        Set<String> paths=list(dcim);
        paths.removeAll(before);
        if(paths.isEmpty()){unchanged=0;previousSize=-1;return null;}
        if(paths.size()!=1)throw new IOException("Multiple new ARW files");
        String path=paths.iterator().next();
        if(observed!=null && !observed.equals(path))throw new IOException("New ARW changed during write");
        observed=path;
        long size=new File(path).length();
        unchanged=size>0 && size==previousSize?unchanged+1:0;
        previousSize=size;
        return unchanged>=3?path:null;
    }
}
