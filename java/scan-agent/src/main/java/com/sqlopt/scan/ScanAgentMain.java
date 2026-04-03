package com.sqlopt.scan;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.StringReader;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.PathMatcher;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.apache.ibatis.builder.xml.XMLMapperBuilder;
import org.apache.ibatis.mapping.BoundSql;
import org.apache.ibatis.mapping.MappedStatement;
import org.apache.ibatis.mapping.ParameterMapping;
import org.apache.ibatis.session.Configuration;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

public class ScanAgentMain {
    private static final Pattern NAMESPACE_PATTERN =
            Pattern.compile("<mapper[^>]*namespace=\\\"([^\\\"]+)\\\"", Pattern.CASE_INSENSITIVE);
    private static final Pattern STMT_PATTERN =
            Pattern.compile("<(select|update|delete|insert)[^>]*id=\\\"([^\\\"]+)\\\"[^>]*>[\\s\\S]*?</\\1>", Pattern.CASE_INSENSITIVE);
    private static final Pattern STMT_META_PATTERN =
            Pattern.compile("<(select|update|delete|insert)[^>]*id=\\\"([^\\\"]+)\\\"[^>]*>([\\s\\S]*?)</\\1>", Pattern.CASE_INSENSITIVE);
    private static final Pattern SQL_FRAGMENT_META_PATTERN =
            Pattern.compile("<sql[^>]*id=\\\"([^\\\"]+)\\\"[^>]*>([\\s\\S]*?)</sql>", Pattern.CASE_INSENSITIVE);
    private static final Pattern SQL_FRAGMENT_PATTERN =
            Pattern.compile("<sql\\b[\\s\\S]*?</sql>", Pattern.CASE_INSENSITIVE);
    private static final Pattern HASH_PLACEHOLDER_PATTERN =
            Pattern.compile("#\\{[^}]+\\}");
    private static final Pattern ORDER_BY_DOLLAR_PATTERN =
            Pattern.compile("(?i)\\border\\s+by\\s*\\$\\{([^}]+)\\}");
    private static final Pattern FOREACH_BLOCK_PATTERN =
            Pattern.compile("(?is)<foreach\\b([^>]*)>([\\s\\S]*?)</foreach>");
    private static final Pattern INCLUDE_PATTERN =
            Pattern.compile("(?is)<include\\b");
    private static final Pattern INCLUDE_BLOCK_PATTERN =
            Pattern.compile("(?is)<include\\b([^>]*)/?>");

    private record ParseResult(List<String> rows, int discoveredCount, boolean degraded) {}

    private static class ScanConfig {
        final List<String> mapperGlobs;
        final String mode;
        final boolean enableClasspathProbe;
        final boolean enableTypeSanitize;
        final boolean statementLevelRecovery;

        ScanConfig(List<String> mapperGlobs, String mode, boolean enableClasspathProbe, boolean enableTypeSanitize, boolean statementLevelRecovery) {
            this.mapperGlobs = mapperGlobs;
            this.mode = mode;
            this.enableClasspathProbe = enableClasspathProbe;
            this.enableTypeSanitize = enableTypeSanitize;
            this.statementLevelRecovery = statementLevelRecovery;
        }
    }

    private static class MapperPieces {
        final String namespace;
        final List<String> fragments;
        final List<StatementPiece> statements;

        MapperPieces(String namespace, List<String> fragments, List<StatementPiece> statements) {
            this.namespace = namespace;
            this.fragments = fragments;
            this.statements = statements;
        }
    }

    private static class StatementPiece {
        final String id;
        final String xml;

        StatementPiece(String id, String xml) {
            this.id = id;
            this.xml = xml;
        }
    }

    private static class ForeachMeta {
        final String collectionExpr;
        final String itemName;
        final List<String> itemPropertyPaths;

        ForeachMeta(String collectionExpr, String itemName, List<String> itemPropertyPaths) {
            this.collectionExpr = collectionExpr == null ? "" : collectionExpr.trim();
            this.itemName = itemName == null ? "item" : itemName.trim();
            this.itemPropertyPaths = itemPropertyPaths == null ? List.of() : List.copyOf(itemPropertyPaths);
        }
    }

    private static class FragmentMeta {
        final String qualifiedRef;
        final List<String> dynamicFeatures;
        final List<String> includeRefs;

        FragmentMeta(String qualifiedRef, List<String> dynamicFeatures, List<String> includeRefs) {
            this.qualifiedRef = qualifiedRef == null ? "" : qualifiedRef;
            this.dynamicFeatures = dynamicFeatures == null ? List.of() : List.copyOf(dynamicFeatures);
            this.includeRefs = includeRefs == null ? List.of() : List.copyOf(includeRefs);
        }
    }

    private static class IncludeResolution {
        final List<String> includeTrace;
        final Map<String, List<String>> includeFragmentFeatures;

        IncludeResolution(List<String> includeTrace, Map<String, List<String>> includeFragmentFeatures) {
            this.includeTrace = includeTrace == null ? List.of() : List.copyOf(includeTrace);
            this.includeFragmentFeatures = includeFragmentFeatures == null ? Map.of() : Map.copyOf(includeFragmentFeatures);
        }
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> argMap = parseArgs(args);
        String projectRoot = argMap.get("--project-root");
        String outJsonl = argMap.get("--out-jsonl");
        String configPath = argMap.get("--config-path");
        if (configPath == null && argMap.containsKey("--config")) {
            configPath = argMap.get("--config");
        }

        if (projectRoot == null || outJsonl == null || configPath == null) {
            emitError("fatal", "SCAN_UNKNOWN_EXIT", "missing required args", null, null, "missing --project-root/--out-jsonl/--config-path", null, false, null, null, null);
            System.exit(20);
        }

        ScanConfig scanConfig = loadScanConfig(Paths.get(configPath));
        Path root = Paths.get(projectRoot);
        List<Path> mapperFiles = findMapperXml(root, scanConfig.mapperGlobs);
        if (mapperFiles.isEmpty()) {
            emitError("fatal", "SCAN_MAPPER_NOT_FOUND", "no mapper xml found", null, null, null, null, false, null, null, null);
            System.exit(20);
        }

        URLClassLoader projectLoader = scanConfig.enableClasspathProbe ? buildProjectClassLoader(root) : null;
        ClassLoader previous = Thread.currentThread().getContextClassLoader();
        if (projectLoader != null) {
            Thread.currentThread().setContextClassLoader(projectLoader);
        }

        List<String> rows = new ArrayList<>();
        boolean degraded = false;
        int discoveredCount = 0;
        int parsedCount = 0;
        try {
            for (Path file : mapperFiles) {
                String xml = Files.readString(file, StandardCharsets.UTF_8);
                discoveredCount += countStatements(xml);
                String namespace = extractNamespace(xml);
                Map<String, FragmentMeta> fragmentMetaMap = parseFragmentMeta(xml, namespace);
                Map<String, StatementMeta> metaMap = parseStatementMeta(xml, namespace, fragmentMetaMap);

                ParseResult parsed = parseMapperWithRecovery(file, xml, namespace, metaMap, scanConfig);
                rows.addAll(parsed.rows());
                parsedCount += parsed.rows().size();
                if (parsed.degraded() || parsed.rows().size() < parsed.discoveredCount()) {
                    degraded = true;
                }
            }
        } finally {
            Thread.currentThread().setContextClassLoader(previous);
            if (projectLoader != null) {
                try {
                    projectLoader.close();
                } catch (Exception ignore) {
                    // no-op
                }
            }
        }

        Path outPath = Paths.get(outJsonl);
        if (outPath.getParent() != null) {
            Files.createDirectories(outPath.getParent());
        }
        Files.write(outPath, rows, StandardCharsets.UTF_8);

        if (rows.isEmpty()) {
            emitError("fatal", "SCAN_XML_PARSE_FATAL", "no sql extracted", null, null, null, null, false, discoveredCount, parsedCount, ratio(discoveredCount, parsedCount));
            System.exit(20);
        }

        if (parsedCount < discoveredCount) {
            emitError(
                    "degradable",
                    "SCAN_STATEMENT_PARSE_DEGRADED",
                    "one or more statements could not be parsed",
                    null,
                    null,
                    null,
                    "summary",
                    false,
                    discoveredCount,
                    parsedCount,
                    ratio(discoveredCount, parsedCount)
            );
            degraded = true;
        }

        if ("strict".equals(scanConfig.mode) && degraded) {
            emitError("fatal", "SCAN_CLASS_RESOLUTION_DEGRADED", "strict mode rejects degraded scan", null, null, null, "strict_gate", false, discoveredCount, parsedCount, ratio(discoveredCount, parsedCount));
            System.exit(20);
        }

        System.exit(degraded ? 10 : 0);
    }

    private static ScanConfig loadScanConfig(Path configPath) {
        String text;
        try {
            text = Files.readString(configPath, StandardCharsets.UTF_8);
        } catch (Exception e) {
            return defaultScanConfig();
        }
        List<String> mapperGlobs = parseMapperGlobs(text);
        if (mapperGlobs.isEmpty()) {
            mapperGlobs = List.of("**/*Mapper.xml", "**/*.xml");
        }
        String mode = parseStringValue(text, "mode", "tolerant").toLowerCase(Locale.ROOT);
        boolean enableClasspathProbe = parseBooleanValue(text, "enable_classpath_probe", true);
        boolean enableTypeSanitize = parseBooleanValue(text, "enable_type_sanitize", true);
        boolean statementLevelRecovery = parseBooleanValue(text, "statement_level_recovery", true);
        return new ScanConfig(mapperGlobs, mode, enableClasspathProbe, enableTypeSanitize, statementLevelRecovery);
    }

    private static ScanConfig defaultScanConfig() {
        return new ScanConfig(List.of("**/*Mapper.xml", "**/*.xml"), "tolerant", true, true, true);
    }

    private static List<String> parseMapperGlobs(String text) {
        List<String> out = new ArrayList<>();
        Matcher m = Pattern.compile("\"mapper_globs\"\\s*:\\s*\\[(.*?)\\]", Pattern.DOTALL).matcher(text);
        if (m.find()) {
            Matcher q = Pattern.compile("\"([^\"]+)\"").matcher(m.group(1));
            while (q.find()) {
                out.add(q.group(1));
            }
            return out;
        }

        String[] lines = text.split("\\r?\\n");
        boolean inMapperGlobs = false;
        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.startsWith("mapper_globs:")) {
                inMapperGlobs = true;
                continue;
            }
            if (inMapperGlobs) {
                if (trimmed.startsWith("-")) {
                    String v = trimmed.substring(1).trim();
                    if ((v.startsWith("\"") && v.endsWith("\"")) || (v.startsWith("'") && v.endsWith("'"))) {
                        v = v.substring(1, v.length() - 1);
                    }
                    if (!v.isBlank()) {
                        out.add(v);
                    }
                    continue;
                }
                if (!trimmed.isBlank() && !line.startsWith(" ") && !line.startsWith("\t")) {
                    break;
                }
            }
        }
        return out;
    }

    private static boolean parseBooleanValue(String text, String key, boolean defaultVal) {
        Matcher m = Pattern.compile("\"" + Pattern.quote(key) + "\"\\s*:\\s*(true|false)", Pattern.CASE_INSENSITIVE).matcher(text);
        if (m.find()) {
            return Boolean.parseBoolean(m.group(1));
        }
        Matcher y = Pattern.compile("(?m)^\\s*" + Pattern.quote(key) + "\\s*:\\s*(true|false)\\s*$", Pattern.CASE_INSENSITIVE).matcher(text);
        if (y.find()) {
            return Boolean.parseBoolean(y.group(1));
        }
        return defaultVal;
    }

    private static String parseStringValue(String text, String key, String defaultVal) {
        Matcher m = Pattern.compile("\"" + Pattern.quote(key) + "\"\\s*:\\s*\"([^\"]+)\"").matcher(text);
        if (m.find()) {
            return m.group(1);
        }
        Matcher y = Pattern.compile("(?m)^\\s*" + Pattern.quote(key) + "\\s*:\\s*([A-Za-z0-9_\\-]+)\\s*$").matcher(text);
        if (y.find()) {
            return y.group(1);
        }
        return defaultVal;
    }

    private static ParseResult parseMapperWithRecovery(Path file, String xml, String namespace, Map<String, StatementMeta> metaMap, ScanConfig scanConfig) {
        List<String> out = new ArrayList<>();
        int discovered = countStatements(xml);
        try {
            out.addAll(parseMapperWithMyBatis(file, xml, metaMap));
            return new ParseResult(out, discovered, false);
        } catch (Exception e) {
            if (!isClassResolutionError(e)) {
                emitError("degradable", "SCAN_STATEMENT_PARSE_DEGRADED", e.getMessage(), file.toString(), null, e.getClass().getName(), "mapper_parse", false, null, null, null);
                return new ParseResult(out, discovered, true);
            }
            emitError("degradable", "SCAN_CLASS_NOT_FOUND", e.getMessage(), file.toString(), null, e.getClass().getName(), "mapper_parse", false, null, null, null);
        }

        if (scanConfig.enableTypeSanitize) {
            String sanitized = sanitizeTypeAttributes(xml);
            try {
                out.addAll(parseMapperWithMyBatis(file, sanitized, metaMap));
                emitError(
                        "degradable",
                        "SCAN_TYPE_ATTR_SANITIZED",
                        "mapper recovered by sanitizing type attributes",
                        file.toString(),
                        null,
                        null,
                        "type_sanitize",
                        true,
                        null,
                        null,
                        null
                );
                return new ParseResult(out, discovered, true);
            } catch (Exception e) {
                emitError("degradable", "SCAN_CLASS_RESOLUTION_DEGRADED", e.getMessage(), file.toString(), null, e.getClass().getName(), "type_sanitize", false, null, null, null);
            }
        }

        if (!scanConfig.statementLevelRecovery) {
            return new ParseResult(out, discovered, true);
        }

        boolean domRecovered = recoverByDom(file, xml, namespace, metaMap, out, scanConfig.enableTypeSanitize);
        if (domRecovered) {
            return new ParseResult(out, discovered, true);
        }

        recoverByRegex(file, xml, namespace, metaMap, out, scanConfig.enableTypeSanitize);
        return new ParseResult(out, discovered, true);
    }

    private static boolean recoverByDom(Path file, String xml, String namespace, Map<String, StatementMeta> metaMap, List<String> out, boolean enableTypeSanitize) {
        MapperPieces pieces;
        try {
            pieces = extractMapperPiecesByDom(xml);
        } catch (Exception e) {
            emitError("degradable", "SCAN_STATEMENT_PARSE_DEGRADED", e.getMessage(), file.toString(), null, e.getClass().getName(), "statement_split_dom", false, null, null, null);
            return false;
        }
        if (pieces.statements.isEmpty()) {
            return false;
        }
        Set<String> seen = new HashSet<>();
        for (StatementPiece piece : pieces.statements) {
            String stmtId = piece.id;
            if (stmtId != null && seen.contains(stmtId)) {
                continue;
            }
            if (stmtId != null) {
                seen.add(stmtId);
            }
            String candidateXml = buildSingleStatementMapper(namespace, pieces.fragments, piece.xml);
            String toParse = enableTypeSanitize ? sanitizeTypeAttributes(candidateXml) : candidateXml;
            try {
                out.addAll(parseMapperWithMyBatis(file, toParse, metaMap));
                emitError("degradable", "SCAN_TYPE_ATTR_SANITIZED", "statement recovered by dom split", file.toString(), stmtId, null, "statement_split_dom", true, null, null, null);
            } catch (Exception ex) {
                String reason = isClassResolutionError(ex) ? "SCAN_CLASS_NOT_FOUND" : "SCAN_STATEMENT_PARSE_DEGRADED";
                emitError("degradable", reason, ex.getMessage(), file.toString(), stmtId, ex.getClass().getName(), "statement_split_dom", false, null, null, null);
            }
        }
        return true;
    }

    private static void recoverByRegex(Path file, String xml, String namespace, Map<String, StatementMeta> metaMap, List<String> out, boolean enableTypeSanitize) {
        List<String> fragments = extractSqlFragments(xml);
        Matcher m = STMT_PATTERN.matcher(xml);
        while (m.find()) {
            String stmtXml = m.group(0);
            String statementId = extractStatementId(stmtXml);
            String candidateXml = buildSingleStatementMapper(namespace, fragments, stmtXml);
            String toParse = enableTypeSanitize ? sanitizeTypeAttributes(candidateXml) : candidateXml;
            try {
                out.addAll(parseMapperWithMyBatis(file, toParse, metaMap));
                emitError("degradable", "SCAN_TYPE_ATTR_SANITIZED", "statement recovered by regex split", file.toString(), statementId, null, "regex_fallback", true, null, null, null);
            } catch (Exception ex) {
                emitError("degradable", "SCAN_STATEMENT_PARSE_DEGRADED", ex.getMessage(), file.toString(), statementId, ex.getClass().getName(), "regex_fallback", false, null, null, null);
            }
        }
    }

    private static MapperPieces extractMapperPiecesByDom(String xml) throws Exception {
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        dbf.setNamespaceAware(false);
        disableUnsafeXmlFeatures(dbf);
        DocumentBuilder db = dbf.newDocumentBuilder();
        db.setEntityResolver((publicId, systemId) -> new InputSource(new StringReader("")));

        Document doc = db.parse(new InputSource(new StringReader(xml)));
        Element root = doc.getDocumentElement();
        String namespace = root.getAttribute("namespace");

        List<String> fragments = new ArrayList<>();
        List<StatementPiece> statements = new ArrayList<>();

        NodeList children = root.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (node.getNodeType() != Node.ELEMENT_NODE) {
                continue;
            }
            String name = node.getNodeName();
            if ("sql".equalsIgnoreCase(name)) {
                fragments.add(nodeToString(node));
                continue;
            }
            if ("select".equalsIgnoreCase(name)
                    || "update".equalsIgnoreCase(name)
                    || "delete".equalsIgnoreCase(name)
                    || "insert".equalsIgnoreCase(name)) {
                String id = ((Element) node).getAttribute("id");
                statements.add(new StatementPiece(id == null || id.isBlank() ? null : id, nodeToString(node)));
            }
        }
        return new MapperPieces(namespace == null || namespace.isBlank() ? "unknown" : namespace, fragments, statements);
    }

    private static void disableUnsafeXmlFeatures(DocumentBuilderFactory dbf) {
        try {
            dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", false);
        } catch (Exception ignore) {
            // no-op
        }
        try {
            dbf.setFeature("http://xml.org/sax/features/external-general-entities", false);
        } catch (Exception ignore) {
            // no-op
        }
        try {
            dbf.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        } catch (Exception ignore) {
            // no-op
        }
        try {
            dbf.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        } catch (Exception ignore) {
            // no-op
        }
    }

    private static String nodeToString(Node node) throws Exception {
        TransformerFactory tf = TransformerFactory.newInstance();
        Transformer transformer = tf.newTransformer();
        transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
        transformer.setOutputProperty(OutputKeys.INDENT, "no");
        java.io.StringWriter writer = new java.io.StringWriter();
        transformer.transform(new DOMSource(node), new StreamResult(writer));
        return writer.toString();
    }

    private static List<String> parseMapperWithMyBatis(Path file, String xml, Map<String, StatementMeta> metaMap) throws Exception {
        Configuration config = new Configuration();
        String resource = file.toString();
        try (InputStream in = new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8))) {
            XMLMapperBuilder parser = new XMLMapperBuilder(in, config, resource, config.getSqlFragments());
            parser.parse();
        }

        List<String> out = new ArrayList<>();
        Set<String> seenStatementIds = new HashSet<>();
        for (MappedStatement ms : config.getMappedStatements()) {
            if (!resource.equals(ms.getResource())) {
                continue;
            }
            String fullId = ms.getId();
            if (seenStatementIds.contains(fullId)) {
                continue;
            }
            seenStatementIds.add(fullId);
            StatementMeta meta = metaMap.getOrDefault(fullId, new StatementMeta("unknown", tail(fullId), false, null, List.of(), List.of(), "", List.of(), List.of(), Map.of()));
            try {
                BoundSql boundSql = ms.getBoundSql(sampleParamsForStatement(meta));
                String normalizedSql = normalize(boundSql.getSql());
                normalizedSql = restoreHashPlaceholders(normalizedSql, meta, boundSql.getParameterMappings());
                normalizedSql = restoreOrderByPlaceholder(normalizedSql, meta);
                if (normalizedSql.isBlank()) {
                    continue;
                }
                out.add(buildSqlUnitRow(file, fullId, ms, meta, normalizedSql, boundSql));
            } catch (Exception e) {
                String reason = isClassResolutionError(e) ? "SCAN_CLASS_NOT_FOUND" : "SCAN_STATEMENT_PARSE_DEGRADED";
                emitError("degradable", reason, e.getMessage(), file.toString(), meta.statementId, e.getClass().getName(), "bound_sql", false, null, null, null);
            }
        }
        return out;
    }

    private static String buildSqlUnitRow(Path file, String fullId, MappedStatement ms, StatementMeta meta, String normalizedSql, BoundSql boundSql) {
        String riskFlags = meta.containsDollar ? "[\"DOLLAR_SUBSTITUTION\"]" : "[]";
        String parameterMappingsJson = buildParameterMappings(boundSql.getParameterMappings());
        return "{"
                + "\"sqlKey\":\"" + esc(fullId) + "\"," 
                + "\"statementKey\":\"" + esc(fullId) + "\"," 
                + "\"xmlPath\":\"" + esc(file.toString()) + "\"," 
                + "\"namespace\":\"" + esc(meta.namespace) + "\"," 
                + "\"statementId\":\"" + esc(meta.statementId) + "\"," 
                + "\"statementType\":\"" + ms.getSqlCommandType().name() + "\"," 
                + "\"sql\":\"" + esc(normalizedSql) + "\"," 
                + "\"templateSql\":\"" + esc(meta.templateSql) + "\","
                + "\"dynamicFeatures\":" + buildStringArray(meta.dynamicFeatures) + ","
                + "\"includeTrace\":" + buildStringArray(meta.includeTrace) + ","
                + "\"dynamicTrace\":" + buildDynamicTrace(meta) + ","
                + "\"parameterMappings\":" + parameterMappingsJson + ","
                + "\"paramExample\":{},"
                + "\"locators\":{\"statementId\":\"" + esc(meta.statementId) + "\"},"
                + "\"riskFlags\":" + riskFlags
                + "}";
    }

    private static URLClassLoader buildProjectClassLoader(Path projectRoot) throws Exception {
        List<URL> urls = new ArrayList<>();
        List<Path> candidates = List.of(
                projectRoot.resolve("target/classes"),
                projectRoot.resolve("target/test-classes"),
                projectRoot.resolve("build/classes/java/main"),
                projectRoot.resolve("build/classes/kotlin/main"),
                projectRoot.resolve("build/resources/main")
        );
        for (Path p : candidates) {
            if (Files.exists(p)) {
                urls.add(p.toUri().toURL());
            }
        }
        addGlobUrls(projectRoot.resolve("target/dependency"), "*.jar", urls);
        addGlobUrls(projectRoot.resolve("build/libs"), "*.jar", urls);
        return new URLClassLoader(urls.toArray(new URL[0]), Thread.currentThread().getContextClassLoader());
    }

    private static void addGlobUrls(Path dir, String glob, List<URL> urls) throws Exception {
        if (!Files.isDirectory(dir)) {
            return;
        }
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(dir, glob)) {
            for (Path p : stream) {
                urls.add(p.toUri().toURL());
            }
        }
    }

    private static String sanitizeTypeAttributes(String xml) {
        String out = xml;
        out = out.replaceAll("(?i)\\s+(resultType|parameterType|javaType|ofType|type)\\s*=\\s*\"[^\"]+\"", " $1=\"java.lang.Object\"");
        out = out.replaceAll("(?i)\\s+typeHandler\\s*=\\s*\"[^\"]+\"", "");
        out = out.replaceAll("(?i)\\s+resultMap\\s*=\\s*\"[^\"]+\"", "");
        return out;
    }

    private static boolean isClassResolutionError(Throwable t) {
        Throwable cur = t;
        while (cur != null) {
            String msg = String.valueOf(cur.getMessage()).toLowerCase(Locale.ROOT);
            if (msg.contains("classnotfoundexception")
                    || msg.contains("error resolving class")
                    || msg.contains("could not resolve type alias")
                    || msg.contains("cannot find class")) {
                return true;
            }
            cur = cur.getCause();
        }
        return false;
    }

    private static String buildSingleStatementMapper(String namespace, List<String> fragments, String stmtXml) {
        StringBuilder sb = new StringBuilder();
        sb.append("<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n");
        sb.append("<!DOCTYPE mapper PUBLIC \"-//mybatis.org//DTD Mapper 3.0//EN\" \"http://mybatis.org/dtd/mybatis-3-mapper.dtd\">\n");
        sb.append("<mapper namespace=\"").append(escAttr(namespace)).append("\">\n");
        for (String frag : fragments) {
            sb.append(frag).append("\n");
        }
        sb.append(stmtXml).append("\n");
        sb.append("</mapper>");
        return sb.toString();
    }

    private static List<String> extractSqlFragments(String xml) {
        List<String> fragments = new ArrayList<>();
        Matcher m = SQL_FRAGMENT_PATTERN.matcher(xml);
        while (m.find()) {
            fragments.add(m.group(0));
        }
        return fragments;
    }

    private static String extractStatementId(String stmtXml) {
        Matcher m = Pattern.compile("id=\\\"([^\\\"]+)\\\"").matcher(stmtXml);
        return m.find() ? m.group(1) : null;
    }

    private static int countStatements(String xml) {
        Matcher m = STMT_META_PATTERN.matcher(xml);
        int count = 0;
        while (m.find()) {
            count++;
        }
        return count;
    }

    private static Map<String, Object> sampleParams() {
        Map<String, Object> params = new HashMap<>();
        params.put("id", 1);
        params.put("name", "demo");
        params.put("status", "ACTIVE");
        params.put("list", Arrays.asList(1, 2, 3));
        params.put("items", Arrays.asList("a", "b"));
        params.put("offset", 0);
        params.put("limit", 10);
        return params;
    }

    private static Map<String, Object> sampleParamsForStatement(StatementMeta meta) {
        Map<String, Object> params = sampleParams();
        if (meta == null || meta.foreachMetas == null || meta.foreachMetas.isEmpty()) {
            return params;
        }
        for (ForeachMeta foreachMeta : meta.foreachMetas) {
            if (foreachMeta == null || foreachMeta.collectionExpr.isBlank()) {
                continue;
            }
            putNestedPath(params, sanitizeCollectionPath(foreachMeta.collectionExpr), buildSampleCollection(foreachMeta));
        }
        return params;
    }

    private static List<Object> buildSampleCollection(ForeachMeta meta) {
        List<Object> values = new ArrayList<>();
        values.add(buildSampleElement(meta, 1));
        values.add(buildSampleElement(meta, 2));
        return values;
    }

    private static Object buildSampleElement(ForeachMeta meta, int idx) {
        if (meta == null || meta.itemPropertyPaths == null || meta.itemPropertyPaths.isEmpty()) {
            return idx;
        }
        Map<String, Object> element = new HashMap<>();
        for (String path : meta.itemPropertyPaths) {
            putNestedPath(element, path, defaultSampleValue(lastPathSegment(path), idx));
        }
        return element;
    }

    private static Object defaultSampleValue(String leafName, int idx) {
        String name = leafName == null ? "" : leafName.trim();
        String lower = name.toLowerCase(Locale.ROOT);
        if (lower.endsWith("id") || "id".equals(lower) || lower.endsWith("ids") || lower.contains("count") || "offset".equals(lower) || "limit".equals(lower)) {
            return idx;
        }
        return "demo" + idx;
    }

    private static String lastPathSegment(String path) {
        if (path == null || path.isBlank()) {
            return "";
        }
        int idx = path.lastIndexOf('.');
        return idx >= 0 ? path.substring(idx + 1) : path;
    }

    private static String sanitizeCollectionPath(String path) {
        if (path == null) {
            return "";
        }
        String out = path.trim();
        if (out.startsWith("_parameter.")) {
            return out.substring("_parameter.".length());
        }
        if ("_parameter".equals(out)) {
            return "";
        }
        return out;
    }

    @SuppressWarnings("unchecked")
    private static void putNestedPath(Map<String, Object> root, String path, Object value) {
        if (root == null || path == null || path.isBlank()) {
            return;
        }
        String[] parts = path.split("\\.");
        Map<String, Object> cur = root;
        for (int i = 0; i < parts.length - 1; i++) {
            String part = parts[i].trim();
            if (part.isBlank()) {
                return;
            }
            Object existing = cur.get(part);
            if (!(existing instanceof Map)) {
                Map<String, Object> child = new HashMap<>();
                cur.put(part, child);
                cur = child;
            } else {
                cur = (Map<String, Object>) existing;
            }
        }
        String leaf = parts[parts.length - 1].trim();
        if (!leaf.isBlank()) {
            cur.put(leaf, value);
        }
    }

    private static String buildParameterMappings(List<ParameterMapping> pms) {
        StringBuilder sb = new StringBuilder();
        sb.append("[");
        for (int i = 0; i < pms.size(); i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append("{\"property\":\"").append(esc(pms.get(i).getProperty())).append("\"}");
        }
        sb.append("]");
        return sb.toString();
    }

    private static String buildStringArray(List<String> values) {
        StringBuilder sb = new StringBuilder();
        sb.append("[");
        if (values != null) {
            for (int i = 0; i < values.size(); i++) {
                if (i > 0) {
                    sb.append(",");
                }
                sb.append("\"").append(esc(values.get(i))).append("\"");
            }
        }
        sb.append("]");
        return sb.toString();
    }

    private static String buildDynamicTrace(StatementMeta meta) {
        if (meta == null) {
            return "null";
        }
        if ((meta.dynamicFeatures == null || meta.dynamicFeatures.isEmpty())
                && (meta.includeTrace == null || meta.includeTrace.isEmpty())) {
            return "null";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("{");
        sb.append("\"statementFeatures\":").append(buildStringArray(meta.dynamicFeatures));
        sb.append(",\"includeFragments\":[");
        for (int i = 0; i < meta.includeTrace.size(); i++) {
            String ref = meta.includeTrace.get(i);
            if (i > 0) {
                sb.append(",");
            }
            sb.append("{\"ref\":\"").append(esc(ref)).append("\"");
            sb.append(",\"dynamicFeatures\":").append(buildStringArray(meta.includeFragmentFeatures.getOrDefault(ref, List.of())));
            sb.append("}");
        }
        sb.append("]}");
        return sb.toString();
    }

    private static String extractNamespace(String xml) {
        Matcher m = NAMESPACE_PATTERN.matcher(xml);
        return m.find() ? m.group(1) : "unknown";
    }

    private static Map<String, FragmentMeta> parseFragmentMeta(String xml, String namespace) {
        Map<String, FragmentMeta> out = new HashMap<>();
        Matcher m = SQL_FRAGMENT_META_PATTERN.matcher(xml);
        while (m.find()) {
            String id = m.group(1);
            String body = m.group(2);
            out.put(qualifyRef(namespace, id), buildFragmentMeta(namespace, id, body));
        }
        return out;
    }

    private static FragmentMeta buildFragmentMeta(String namespace, String fragmentId, String body) {
        String qualifiedRef = qualifyRef(namespace, fragmentId);
        return new FragmentMeta(qualifiedRef, extractDynamicFeatures(body), extractIncludeRefs(body, namespace));
    }

    private static Map<String, StatementMeta> parseStatementMeta(String xml, String namespace, Map<String, FragmentMeta> fragmentMetaMap) {
        Map<String, StatementMeta> out = new HashMap<>();
        Matcher m = STMT_META_PATTERN.matcher(xml);
        while (m.find()) {
            String id = m.group(2);
            String body = m.group(3);
            out.put(namespace + "." + id, buildStatementMeta(namespace, id, body, fragmentMetaMap));
        }
        return out;
    }

    private static StatementMeta buildStatementMeta(String namespace, String statementId, String body, Map<String, FragmentMeta> fragmentMetaMap) {
        boolean containsDollar = body != null && body.contains("${");
        String orderByDollarKey = extractOrderByDollarKey(body);
        List<String> hashPlaceholders = extractHashPlaceholders(body);
        List<ForeachMeta> foreachMetas = new ArrayList<>();
        List<String> dynamicFeatures = List.of();
        List<String> includeTrace = List.of();
        Map<String, List<String>> includeFragmentFeatures = Map.of();
        if (body != null) {
            foreachMetas = extractForeachMetas(body);
            dynamicFeatures = extractDynamicFeatures(body);
            IncludeResolution resolution = resolveIncludeTrace(namespace, extractIncludeRefs(body, namespace), fragmentMetaMap);
            includeTrace = resolution.includeTrace;
            includeFragmentFeatures = resolution.includeFragmentFeatures;
        }
        return new StatementMeta(
                namespace,
                statementId,
                containsDollar,
                orderByDollarKey,
                hashPlaceholders,
                foreachMetas,
                body == null ? "" : body,
                dynamicFeatures,
                includeTrace,
                includeFragmentFeatures
        );
    }

    private static String extractOrderByDollarKey(String body) {
        if (body == null || body.isBlank()) {
            return null;
        }
        Matcher m = ORDER_BY_DOLLAR_PATTERN.matcher(body);
        if (m.find()) {
            return m.group(1);
        }
        return null;
    }

    private static List<String> extractHashPlaceholders(String body) {
        if (body == null || body.isBlank()) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        Matcher m = HASH_PLACEHOLDER_PATTERN.matcher(body);
        while (m.find()) {
            out.add(m.group());
        }
        return out;
    }

    private static IncludeResolution resolveIncludeTrace(String namespace, List<String> directRefs, Map<String, FragmentMeta> fragmentMetaMap) {
        LinkedHashSet<String> trace = new LinkedHashSet<>();
        Map<String, List<String>> featureMap = new HashMap<>();
        if (directRefs != null) {
            for (String ref : directRefs) {
                resolveIncludeRef(namespace, ref, fragmentMetaMap, trace, featureMap, new HashSet<>());
            }
        }
        return new IncludeResolution(new ArrayList<>(trace), featureMap);
    }

    private static void resolveIncludeRef(
            String namespace,
            String ref,
            Map<String, FragmentMeta> fragmentMetaMap,
            LinkedHashSet<String> trace,
            Map<String, List<String>> featureMap,
            Set<String> stack
    ) {
        String qualifiedRef = qualifyRef(namespace, ref);
        if (qualifiedRef.isBlank()) {
            return;
        }
        trace.add(qualifiedRef);
        FragmentMeta fragment = fragmentMetaMap.get(qualifiedRef);
        if (fragment == null) {
            featureMap.putIfAbsent(qualifiedRef, List.of());
            return;
        }
        featureMap.putIfAbsent(qualifiedRef, fragment.dynamicFeatures);
        if (stack.contains(qualifiedRef)) {
            return;
        }
        stack.add(qualifiedRef);
        for (String nestedRef : fragment.includeRefs) {
            resolveIncludeRef(namespace, nestedRef, fragmentMetaMap, trace, featureMap, stack);
        }
        stack.remove(qualifiedRef);
    }

    private static List<String> extractDynamicFeatures(String body) {
        if (body == null || body.isBlank()) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        addDynamicFeature(out, body, "FOREACH", "(?is)<foreach\\b");
        addDynamicFeature(out, body, "INCLUDE", INCLUDE_PATTERN);
        addDynamicFeature(out, body, "IF", "(?is)<if\\b");
        addDynamicFeature(out, body, "CHOOSE", "(?is)<choose\\b");
        addDynamicFeature(out, body, "WHERE", "(?is)<where\\b");
        addDynamicFeature(out, body, "TRIM", "(?is)<trim\\b");
        addDynamicFeature(out, body, "SET", "(?is)<set\\b");
        addDynamicFeature(out, body, "BIND", "(?is)<bind\\b");
        return out;
    }

    private static List<String> extractIncludeRefs(String body, String namespace) {
        if (body == null || body.isBlank()) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        Matcher m = INCLUDE_BLOCK_PATTERN.matcher(body);
        while (m.find()) {
            String ref = extractAttr(m.group(1), "refid");
            String qualifiedRef = qualifyRef(namespace, ref);
            if (!qualifiedRef.isBlank() && !out.contains(qualifiedRef)) {
                out.add(qualifiedRef);
            }
        }
        return out;
    }

    private static String qualifyRef(String namespace, String ref) {
        if (ref == null) {
            return "";
        }
        String trimmed = ref.trim();
        if (trimmed.isBlank()) {
            return "";
        }
        if (trimmed.contains(".")) {
            return trimmed;
        }
        if (namespace == null || namespace.isBlank()) {
            return trimmed;
        }
        return namespace + "." + trimmed;
    }

    private static void addDynamicFeature(List<String> out, String body, String feature, String regex) {
        addDynamicFeature(out, body, feature, Pattern.compile(regex));
    }

    private static void addDynamicFeature(List<String> out, String body, String feature, Pattern pattern) {
        if (pattern.matcher(body).find()) {
            out.add(feature);
        }
    }

    private static List<ForeachMeta> extractForeachMetas(String body) {
        List<ForeachMeta> out = new ArrayList<>();
        if (body == null || body.isBlank()) {
            return out;
        }
        Matcher m = FOREACH_BLOCK_PATTERN.matcher(body);
        while (m.find()) {
            String attrs = m.group(1);
            String foreachBody = m.group(2);
            String collection = extractAttr(attrs, "collection");
            if (collection == null || collection.isBlank()) {
                continue;
            }
            String item = extractAttr(attrs, "item");
            out.add(new ForeachMeta(collection, item, extractItemPropertyPaths(foreachBody, item)));
        }
        return out;
    }

    private static String extractAttr(String attrs, String name) {
        if (attrs == null || attrs.isBlank() || name == null || name.isBlank()) {
            return null;
        }
        Matcher dbl = Pattern.compile("(?i)\\b" + Pattern.quote(name) + "\\s*=\\s*\"([^\"]+)\"").matcher(attrs);
        if (dbl.find()) {
            return dbl.group(1);
        }
        Matcher sgl = Pattern.compile("(?i)\\b" + Pattern.quote(name) + "\\s*=\\s*'([^']+)'").matcher(attrs);
        if (sgl.find()) {
            return sgl.group(1);
        }
        return null;
    }

    private static List<String> extractItemPropertyPaths(String foreachBody, String itemName) {
        if (foreachBody == null || foreachBody.isBlank()) {
            return List.of();
        }
        String item = (itemName == null || itemName.isBlank()) ? "item" : itemName.trim();
        Pattern p = Pattern.compile("#\\{\\s*" + Pattern.quote(item) + "(?:\\.([A-Za-z0-9_$.]+))?\\b[^}]*\\}");
        Matcher m = p.matcher(foreachBody);
        Set<String> out = new LinkedHashSet<>();
        while (m.find()) {
            String prop = m.group(1);
            if (prop != null && !prop.isBlank()) {
                out.add(prop.trim());
            }
        }
        return new ArrayList<>(out);
    }

    private static List<Path> findMapperXml(Path root, List<String> mapperGlobs) throws Exception {
        List<PathMatcher> matchers = new ArrayList<>();
        for (String glob : mapperGlobs) {
            String normalized = glob.replace("\\\\", "/");
            matchers.add(FileSystems.getDefault().getPathMatcher("glob:" + normalized));
        }
        Set<Path> out = new LinkedHashSet<>();
        try (var walk = Files.walk(root)) {
            walk.filter(Files::isRegularFile)
                    .filter(p -> p.toString().endsWith(".xml"))
                    .forEach(
                            p -> {
                                Path rel = root.relativize(p);
                                String relNorm = rel.toString().replace("\\\\", "/");
                                Path relPath = Paths.get(relNorm);
                                for (PathMatcher matcher : matchers) {
                                    if (matcher.matches(relPath)) {
                                        out.add(p);
                                        break;
                                    }
                                }
                            }
                    );
        }
        return new ArrayList<>(out);
    }

    private static String normalize(String s) {
        return s == null ? "" : s.replaceAll("\\s+", " ").trim();
    }

    private static String restoreOrderByPlaceholder(String sql, StatementMeta meta) {
        if (sql == null || meta == null) {
            return sql;
        }
        if (sql.contains("${")) {
            return sql;
        }
        if (sql.matches("(?is).*\\border\\s+by\\s*$") && meta.containsDollar) {
            String key = (meta.orderByDollarKey == null || meta.orderByDollarKey.isBlank()) ? "orderBy" : meta.orderByDollarKey;
            return sql + " ${" + key + "}";
        }
        return sql;
    }

    private static String restoreHashPlaceholders(String sql, StatementMeta meta, List<ParameterMapping> parameterMappings) {
        if (sql == null || meta == null || sql.contains("#{")) {
            return sql;
        }
        if (sql.indexOf('?') < 0) {
            return sql;
        }
        List<String> placeholders = derivePlaceholders(parameterMappings);
        if (placeholders.isEmpty()) {
            placeholders = meta.hashPlaceholders == null ? List.of() : meta.hashPlaceholders;
        }
        if (placeholders.isEmpty()) {
            return sql;
        }
        StringBuilder out = new StringBuilder();
        int idx = 0;
        for (int i = 0; i < sql.length(); i++) {
            char ch = sql.charAt(i);
            if (ch == '?') {
                if (idx >= placeholders.size()) {
                    return sql;
                }
                out.append(placeholders.get(idx++));
            } else {
                out.append(ch);
            }
        }
        if (idx != placeholders.size()) {
            return sql;
        }
        return out.toString();
    }

    private static List<String> derivePlaceholders(List<ParameterMapping> parameterMappings) {
        if (parameterMappings == null || parameterMappings.isEmpty()) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        for (ParameterMapping pm : parameterMappings) {
            if (pm == null) {
                continue;
            }
            String property = pm.getProperty();
            if (property == null || property.isBlank()) {
                continue;
            }
            out.add(toPlaceholder(property));
        }
        return out;
    }

    private static String toPlaceholder(String property) {
        String normalized = normalizeForeachProperty(property);
        return "#{" + normalized + "}";
    }

    private static String normalizeForeachProperty(String property) {
        if (property == null) {
            return "";
        }
        Matcher m = Pattern.compile("^__frch_([A-Za-z0-9_]+)_\\d+(\\..+)?$").matcher(property.trim());
        if (m.matches()) {
            String item = m.group(1);
            String suffix = m.group(2) == null ? "" : m.group(2);
            return item + suffix;
        }
        return property.trim();
    }

    private static String tail(String fullId) {
        int idx = fullId.lastIndexOf('.');
        return idx >= 0 ? fullId.substring(idx + 1) : fullId;
    }

    private static double ratio(int discoveredCount, int parsedCount) {
        if (discoveredCount <= 0) {
            return 1.0;
        }
        return (double) parsedCount / (double) discoveredCount;
    }

    private static void emitError(
            String severity,
            String reasonCode,
            String message,
            String xmlPath,
            String statementId,
            String exception,
            String recoveryAction,
            boolean recovered,
            Integer discoveredCount,
            Integer parsedCount,
            Double successRatio
    ) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"phase\":\"scan\",\"severity\":\"").append(esc(severity)).append("\"");
        sb.append(",\"reason_code\":\"").append(esc(reasonCode)).append("\"");
        sb.append(",\"message\":\"").append(esc(message == null ? "" : message)).append("\"");
        if (xmlPath != null) {
            sb.append(",\"xml_path\":\"").append(esc(xmlPath)).append("\"");
            sb.append(",\"mapper_path\":\"").append(esc(xmlPath)).append("\"");
        }
        if (statementId != null) {
            sb.append(",\"statement_id\":\"").append(esc(statementId)).append("\"");
        }
        if (exception != null) {
            sb.append(",\"exception\":\"").append(esc(exception)).append("\"");
        }
        if (recoveryAction != null) {
            sb.append(",\"recovery_action\":\"").append(esc(recoveryAction)).append("\"");
            sb.append(",\"recovered\":").append(recovered ? "true" : "false");
        }
        if (discoveredCount != null) {
            sb.append(",\"discovered_count\":").append(discoveredCount);
        }
        if (parsedCount != null) {
            sb.append(",\"parsed_count\":").append(parsedCount);
        }
        if (successRatio != null) {
            sb.append(",\"success_ratio\":").append(String.format(Locale.ROOT, "%.6f", successRatio));
        }
        sb.append("}");
        System.err.println(sb);
    }

    private static String esc(String s) {
        return s == null ? "" : s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ").replace("\r", " ");
    }

    private static String escAttr(String s) {
        return esc(s).replace("<", "&lt;").replace(">", "&gt;");
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> m = new HashMap<>();
        for (int i = 0; i < args.length - 1; i += 2) {
            m.put(args[i], args[i + 1]);
        }
        return m;
    }

    private static class StatementMeta {
        final String namespace;
        final String statementId;
        final boolean containsDollar;
        final String orderByDollarKey;
        final List<String> hashPlaceholders;
        final List<ForeachMeta> foreachMetas;
        final String templateSql;
        final List<String> dynamicFeatures;
        final List<String> includeTrace;
        final Map<String, List<String>> includeFragmentFeatures;

        StatementMeta(
                String namespace,
                String statementId,
                boolean containsDollar,
                String orderByDollarKey,
                List<String> hashPlaceholders,
                List<ForeachMeta> foreachMetas,
                String templateSql,
                List<String> dynamicFeatures,
                List<String> includeTrace,
                Map<String, List<String>> includeFragmentFeatures
        ) {
            this.namespace = namespace;
            this.statementId = statementId;
            this.containsDollar = containsDollar;
            this.orderByDollarKey = orderByDollarKey;
            this.hashPlaceholders = hashPlaceholders == null ? List.of() : List.copyOf(hashPlaceholders);
            this.foreachMetas = foreachMetas == null ? List.of() : List.copyOf(foreachMetas);
            this.templateSql = templateSql == null ? "" : templateSql;
            this.dynamicFeatures = dynamicFeatures == null ? List.of() : List.copyOf(dynamicFeatures);
            this.includeTrace = includeTrace == null ? List.of() : List.copyOf(includeTrace);
            this.includeFragmentFeatures = includeFragmentFeatures == null ? Map.of() : Map.copyOf(includeFragmentFeatures);
        }
    }
}
