# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2023-11-19

### Added
- Added `GetMessagesWithMedia` tool to retrieve messages containing media (images, videos, documents, audio)
- Added `RequestUserMedia` tool to request and receive various media types from users
- Maintained backward compatibility with `RequestUserPhotos` tool
- Added support for retrieving thumbnails from videos
- Added support for downloading and handling document media

## [0.1.2] - 2023-10-26

### Fixed
- Fixed runtime error when trying to import xdg_base_dirs.

## [0.1.1] - 2023-09-23

### Added
- Initial release.