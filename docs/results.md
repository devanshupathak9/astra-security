# Teacher -> student results

Teacher: openai/gpt-oss-120b (strict recall 74%, lenient 100%)  
Labels: 19   Runs per condition: 1   Lessons: 12

## Strict recall (right file and right category)
| student | before | placebo | after | lift vs before | lift vs placebo |
|---|---|---|---|---|---|
| openai/gpt-oss-20b | 68% ± 0 | 68% ± 0 | 74% ± 0 | **+5 pts** | +5 pts |

## Lenient recall (right file, any category)
| student | before | placebo | after | lift vs before | lift vs placebo |
|---|---|---|---|---|---|
| openai/gpt-oss-20b | 95% ± 0 | 89% ± 0 | 95% ± 0 | **+0 pts** | +5 pts |

## Per bug: runs where the student found it (strict), before -> placebo -> after
[T] = the teacher found it

    [T]  1. Hardcoded Credentials                           ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T]  2. Insufficient URL Validation (deep link loads a  ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
         3. Weak Host Validation Check                      ai/gpt-oss-20b: 0/1 -> 0/1 -> 0/1
    [T]  4. Arbitrary Code Execution via third-party packa  ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T]  5. Access to Protected Components (embedded inten  ai/gpt-oss-20b: 1/1 -> 0/1 -> 1/1
         6. Unprotected Data URIs (intent data passed to l  ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T]  7. Theft of Arbitrary Files via ChooserActivity    ai/gpt-oss-20b: 0/1 -> 1/1 -> 1/1
         8. Using Components with Known Vulnerabilities     ai/gpt-oss-20b: 0/1 -> 0/1 -> 0/1
    [T]  9. Insecure Broadcast Receiver (registered in exp  ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T] 10. AWS Cognito Misconfiguration                    ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T] 11. Insecure use of FilePaths in FileProvider       ai/gpt-oss-20b: 0/1 -> 0/1 -> 1/1
        12. Implicit Intent Broadcast with Sensitive Data   ai/gpt-oss-20b: 0/1 -> 0/1 -> 0/1
        13. Intercepting Implicit Intent to Load Arbitrary  ai/gpt-oss-20b: 1/1 -> 1/1 -> 0/1
    [T] 14. Insecure setResult in Exported Activity         ai/gpt-oss-20b: 0/1 -> 0/1 -> 1/1
    [T] 15. Insecure Content Provider                       ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T] 16. Lack of SSL Certificate Validation              ai/gpt-oss-20b: 1/1 -> 1/1 -> 0/1
    [T] 17. Insecure WebView Properties Enabled             ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T] 18. Insecure Data Storage (plaintext credentials)   ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1
    [T] 19. Insecure Logging (credentials in logcat)        ai/gpt-oss-20b: 1/1 -> 1/1 -> 1/1

## Precision and finding counts (unlisted real bugs count as wrong)
- openai/gpt-oss-20b: before 59% (22.0 findings), placebo 52% (25.0 findings), after 47% (30.0 findings)