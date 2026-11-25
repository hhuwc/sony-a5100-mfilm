package org.mfilm.sony;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.stream.Stream;

public final class CaptureFilesTest {
    private static void check(boolean condition) {
        if(!condition)throw new AssertionError();
    }
    private interface Probe { void run() throws IOException; }
    private static void rejects(Probe probe) throws IOException {
        try{probe.run();}catch(IOException expected){return;}
        throw new AssertionError("expected card error");
    }
    private static void settle(CaptureFiles tracker,File dcim,Path file) throws IOException {
        for(int i=0;i<3;i++)check(tracker.stableFile(dcim)==null);
        check(file.toString().equals(tracker.stableFile(dcim)));
    }

    public static void main(String[] args) throws Exception {
        Path root=Files.createTempDirectory("mfilm-dcf");
        try{
            Path base=root.resolve("DCIM");
            File dcim=base.toFile();
            rejects(()->new CaptureFiles(dcim));
            Path a=Files.createDirectories(base.resolve("100MSDCF"));
            Files.write(a.resolve("DSC00001.ARW"),new byte[10]);
            CaptureFiles tracker=new CaptureFiles(dcim);
            Files.write(a.resolve("DSC00002.JPG"),new byte[20]);
            Path other=Files.createDirectories(base.resolve("PRIVATE"));
            Files.write(other.resolve("DSC00002.ARW"),new byte[20]);
            check(tracker.stableFile(dcim)==null);
            Path f=a.resolve("DSC00002.ARW");
            Files.createFile(f);
            for(int i=0;i<5;i++)check(tracker.stableFile(dcim)==null);
            Files.write(f,new byte[10]);
            check(tracker.stableFile(dcim)==null);
            Files.write(f,new byte[20]);
            settle(tracker,dcim,f);
            Files.delete(f);
            check(tracker.stableFile(dcim)==null);
            Files.write(f,new byte[20]);
            settle(tracker,dcim,f);
            Path b=Files.createDirectories(base.resolve("101MSDCF"));
            CaptureFiles rollover=new CaptureFiles(dcim);
            Path second=b.resolve("DSC00002.ARW");
            Files.write(second,new byte[10]);
            settle(rollover,dcim,second);
            rejects(()->tracker.stableFile(dcim));
            Files.delete(f);
            rejects(()->tracker.stableFile(dcim));
            System.out.println("PASS DCF snapshot, growth and disappearance, rollover, ambiguous and changed ARW paths");
        }finally{
            try(Stream<Path> tree=Files.walk(root)){
                Path[] paths=tree.sorted(Comparator.reverseOrder()).toArray(Path[]::new);
                for(Path p:paths)Files.delete(p);
            }
        }
    }
}
