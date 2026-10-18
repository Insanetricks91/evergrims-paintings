import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import javax.imageio.*;
import javax.imageio.metadata.*;
import javax.imageio.stream.*;
import org.w3c.dom.*;

import com.loohp.imageframe.libs.com.madgag.gif.fmsware.GifDecoder;
import com.loohp.imageframe.utils.MapUtils;
import org.bukkit.map.MapPalette;

/**
 * Independent decoders for egwpix output, using the exact code the live server runs:
 *   gif   <file> <wBlocks> <hBlocks> : ImageFrame's bundled madgag GifDecoder (its first GIF path) and
 *                                     javax ImageIO (its second), RGB hash per frame, delays, loop count,
 *                                     and the map-colour bytes ImageFrame would store
 *                                     (MapUtils.resize + MapUtils.toMapPaletteBytes(img, null) = nearest-color).
 *   png   <file> <wBlocks> <hBlocks> : ImageIO read (what ImageFrame uses for PNG) + the same map bytes.
 *   match <file>                     : Paper MapPalette.matchColor for each "r g b" line.
 */
public class GifCheck {
    static String hex(byte[] b) throws Exception {
        byte[] d = MessageDigest.getInstance("SHA-256").digest(b);
        StringBuilder sb = new StringBuilder();
        for (byte x : d) sb.append(String.format("%02x", x));
        return sb.substring(0, 24);
    }

    static String rgbHash(BufferedImage im) throws Exception {
        int w = im.getWidth(), h = im.getHeight();
        byte[] b = new byte[w * h * 3];
        int k = 0, minA = 255;
        for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
            int p = im.getRGB(x, y);
            minA = Math.min(minA, p >>> 24);
            b[k++] = (byte) (p >> 16); b[k++] = (byte) (p >> 8); b[k++] = (byte) p;
        }
        return hex(b) + " " + w + "x" + h + " minAlpha=" + minA;
    }

    static String pipe = "imageframe";

    static String idsHash(BufferedImage im, int bw, int bh) throws Exception {
        byte[] ids;
        try {
            BufferedImage r = MapUtils.resize(im, bw, bh);
            ids = MapUtils.toMapPaletteBytes(r, null);
        } catch (Throwable t) {
            pipe = "fallback(" + t.getClass().getSimpleName() + ")";
            ids = MapPalette.imageToBytes(im);
        }
        return hex(ids);
    }

    public static void main(String[] a) throws Exception {
        System.setProperty("java.awt.headless", "true");
        String mode = a[0];
        if (mode.equals("match")) {
            StringBuilder sb = new StringBuilder();
            for (String line : Files.readAllLines(Paths.get(a[1]))) {
                if (line.isBlank()) continue;
                String[] s = line.trim().split("\\s+");
                sb.append(MapPalette.matchColor(Integer.parseInt(s[0]), Integer.parseInt(s[1]), Integer.parseInt(s[2])) & 0xff).append('\n');
            }
            System.out.print(sb);
            return;
        }
        int bw = Integer.parseInt(a[2]), bh = Integer.parseInt(a[3]);
        if (mode.equals("png")) {
            BufferedImage im = ImageIO.read(new File(a[1]));
            System.out.println("PNG " + rgbHash(im) + " ids=" + idsHash(im, bw, bh) + " pipe=" + pipe);
            return;
        }
        // madgag (ImageFrame GifReader.readGifMethodMadgag)
        GifDecoder d = new GifDecoder();
        int st = d.read(new BufferedInputStream(new FileInputStream(a[1])));
        System.out.println("MADGAG status=" + st + " frames=" + d.getFrameCount() + " loop=" + d.getLoopCount());
        for (int i = 0; i < d.getFrameCount(); i++) {
            BufferedImage f = d.getFrame(i);
            System.out.println("M " + i + " " + d.getDelay(i) + " " + rgbHash(f) + " ids=" + idsHash(f, bw, bh));
        }
        // javax ImageIO (ImageFrame GifReader.readGifMethodJavaX)
        ImageReader r = ImageIO.getImageReadersByFormatName("gif").next();
        r.setInput(ImageIO.createImageInputStream(new File(a[1])));
        int n = r.getNumImages(true);
        System.out.println("JAVAX frames=" + n);
        for (int i = 0; i < n; i++) {
            BufferedImage f = r.read(i);
            IIOMetadataNode root = (IIOMetadataNode) r.getImageMetadata(i).getAsTree("javax_imageio_gif_image_1.0");
            IIOMetadataNode gce = (IIOMetadataNode) root.getElementsByTagName("GraphicControlExtension").item(0);
            int delay = Integer.parseInt(gce.getAttribute("delayTime")) * 10;
            String loop = "";
            NodeList apps = root.getElementsByTagName("ApplicationExtension");
            for (int k = 0; k < apps.getLength(); k++) {
                IIOMetadataNode app = (IIOMetadataNode) apps.item(k);
                if ("NETSCAPE".equals(app.getAttribute("applicationID"))) {
                    byte[] u = (byte[]) app.getUserObject();
                    loop = " loop=" + ((u[1] & 0xff) | ((u[2] & 0xff) << 8));
                }
            }
            System.out.println("J " + i + " " + delay + " " + rgbHash(f) + " disposal=" + gce.getAttribute("disposalMethod") + loop);
        }
        System.out.println("PIPE " + pipe);
    }
}
