# 거래처 계좌 변경 통제 입력자료

이 폴더의 CSV 6종은 2026년 8월 국내 거래처 계좌 변경 업무를 본뜬 교육용 합성자료입니다. 모든 회사명과 사용자명은 `가상`으로 표시했으며 실제 회사 정보와 개인정보를 포함하지 않습니다. 사업자등록번호와 계좌번호는 마스킹된 표시값만 사용하고 자료 연결은 `vendor_id`, `request_id`, `change_id`, `account_token`으로 수행합니다.

## 고정 결과

- 전체 모집단: 30건
- 입력 오류: 1건 (`CHG-2608-030`의 `vendor_id` 누락과 잘못된 변경 시각)
- 유효 데이터: 29건
- 정상: 21건 (`CHG-2608-001`–`CHG-2608-021`)
- 검토 필요: 8건 (`CHG-2608-022`–`CHG-2608-029`)

CSV는 실행할 때 생성하지 않는 고정 자료이며 국내 Excel에서 열기 쉬운 UTF-8 BOM으로 저장합니다. 모든 날짜·시각은 `YYYY-MM-DD HH:mm:ss`, 금액은 쉼표와 통화기호가 없는 원 단위 정수입니다.

## 파일과 연결 기준

| 파일 | 업무상 의미 | 주요 연결값 |
| --- | --- | --- |
| `vendor_changes.csv` | 계좌 변경 모집단과 요청·반영 정보 | `change_id`, `vendor_id`, `request_id` |
| `vendor_master.csv` | ERP 거래처 마스터와 현재 계좌 | `vendor_id`, `current_account_token` |
| `change_approvals.csv` | 최종 승인과 승인 계좌 | `change_id`, `approved_account_token` |
| `evidence_register.csv` | 요청별 증빙 등록부 메타데이터 | `request_id`, `document_account_token` |
| `payment_requests.csv` | 변경과 연결된 지급 참고정보 | `change_id`, `vendor_id` |
| `user_roles.csv` | 요청자·승인자·변경자 이름과 역할 | `user_id` |

행 번호나 이름으로 연결하지 않습니다. 증빙 상태와 변경 직후 지급 정보는 화면의 참고정보이며 R-02–R-04 핵심 판정 건수에는 영향을 주지 않습니다.

## 필드 설명

### `vendor_changes.csv`

- `change_id`, `case_id`: 변경과 교육 사례 식별자
- `vendor_id`, `request_id`: 거래처와 요청 연결 식별자
- `requested_at`, `requested_by`: 요청 시각과 요청 사용자 ID
- `before_account_token`, `requested_account_token`: 변경 전 계좌와 요청 계좌의 합성 토큰
- `changed_at`, `changed_by`: ERP 반영 시각과 변경 사용자 ID
- `change_reason`: 교육용 변경 사유

### `vendor_master.csv`

- `vendor_id`, `vendor_name`: 거래처 식별자와 가상 거래처명
- `business_registration_no_masked`: 마스킹된 사업자등록번호 표시값
- `vendor_status`, `vendor_type`: 거래처 상태와 유형
- `bank_code`, `bank_name`: 국내 은행 코드와 은행명
- `account_holder`: 교육용 가상 예금주명
- `current_account_masked`, `current_account_token`: 마스킹 계좌 표시값과 ERP 현재 계좌 토큰
- `last_updated_at`, `last_updated_by`: 최종 반영 시각과 사용자 ID

### `change_approvals.csv`

- `approval_id`, `change_id`: 승인과 변경 연결 식별자
- `approval_stage`, `decision`: 승인 단계와 결정
- `approved_at`, `approved_by`: 승인 시각과 최종 승인자 ID
- `approved_account_token`: 승인된 계좌의 합성 토큰
- `approval_note`: 교육용 승인 메모

### `evidence_register.csv`

- `evidence_id`, `request_id`: 증빙과 요청 연결 식별자
- `document_type`, `document_name`: 국내 계좌 변경 업무의 합성 증빙 유형과 문서명
- `document_status`: `원본대조 확인`, `사본 확인`, `미수취`, `추가 확인` 상태
- `issued_date`, `received_at`, `verified_at`, `verified_by`: 발행·수취·확인 시각과 확인자 ID
- `document_account_token`: 문서에 연결된 합성 계좌 토큰
- `storage_ref`, `note`: 실제 파일이 아닌 교육용 참조값과 메모

### `payment_requests.csv`

- `payment_id`, `vendor_id`, `change_id`: 지급과 거래처 변경 연결 식별자
- `requested_at`, `scheduled_date`: 지급 요청과 예정 시각
- `amount_krw`, `payment_status`, `payment_purpose`: 원화 금액과 상태·목적
- `beneficiary_account_token`: 수취 계좌의 합성 토큰
- `requested_by`: 지급 요청 사용자 ID

### `user_roles.csv`

- `user_id`, `user_name`: 사용자 식별자와 교육용 가상 이름
- `department`, `position`, `role_name`: 부서·직급·업무 역할
- `user_status`, `valid_from`, `valid_to`: 계정 상태와 역할 유효기간
- `permissions`: 세미콜론으로 구분한 교육용 권한 코드
