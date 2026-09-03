# Keep rules intentionally minimal so R8 can optimize/shrink/obfuscate aggressively.
# OAK native Android uses no reflection-based JSON or DI frameworks.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
